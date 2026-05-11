#!/usr/bin/env python3
"""
DeepStream Bridge Application — Headcount AI
=============================================

Manages a DeepStream GStreamer pipeline with dynamic RTSP source management.
Runs inside the Docker container and exposes:

  1. FastAPI REST API (port 8010) for add/remove RTSP sources
  2. Redis PUB for per-camera detection metadata  (channel: ds_data_{camera_id})
  3. Redis SET for per-camera annotated JPEG frames (key: ds_frame:{camera_id})

Architecture:
  [uridecodebin per source] → nvstreammux → nvinfer (YOLO) → nvtracker (NvDCF)
    → nvvideoconvert → nvdsosd → nvvideoconvert → capsfilter(RGBA) → fakesink

Usage (inside container):
  python3 ds_app.py
"""

import sys
import os
import time
import json
import threading
import logging

# DeepStream Python bindings
sys.path.append("/opt/nvidia/deepstream/deepstream/lib")

# pyrefly: ignore [missing-import]
import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstRtspServer", "1.0")
# pyrefly: ignore [missing-import]
from gi.repository import Gst, GstRtspServer, GLib

# pyrefly: ignore [missing-import]
import pyds
import numpy as np
import cv2
import redis

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
# pyrefly: ignore [missing-import]
import uvicorn

from ds_config import (
    REDIS_HOST, REDIS_PORT, API_PORT, MAX_SOURCES,
    STREAMMUX_BATCH_SIZE, STREAMMUX_WIDTH, STREAMMUX_HEIGHT,
    STREAMMUX_BATCHED_PUSH_TIMEOUT, INFER_CONFIG, TRACKER_CONFIG,
    FRAME_PUBLISH_INTERVAL, JPEG_QUALITY, FRAME_TTL_SECONDS,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ds_bridge")

# ---------------------------------------------------------------------------
# Initialize GStreamer
# ---------------------------------------------------------------------------
Gst.init(None)


# ===========================================================================
# Source tracking
# ===========================================================================
class SourceInfo:
    """Tracks a single RTSP source inside the pipeline."""

    def __init__(self, camera_id: int, url: str, source_id: int, source_bin):
        self.camera_id = camera_id
        self.url = url
        self.source_id = source_id      # Slot index in streammux (0..MAX_SOURCES-1)
        self.source_bin = source_bin
        self.is_live = False
        self.fps = 0
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.sinkpad = None
        self.count_history = [] # For smoothing jitter
        self.stable_count = 0


# ===========================================================================
# DeepStream Pipeline Manager
# ===========================================================================
class DeepStreamBridge:
    """
    Builds and manages the DeepStream GStreamer pipeline.

    Sources are added/removed at runtime via add_source() / remove_source().
    Detection metadata and annotated frames are pushed to Redis.
    """

    def __init__(self):
        self.pipeline = None
        self.streammux = None


        self.tiler = None
        self.loop = None

        # Enable RTSP keep‑alive by default (most modern servers support it).
        # Some legacy servers cannot handle keep‑alive packets; set the
        # environment variable DO_RTSP_KEEP_ALIVE="false" to disable it.
        self.do_rtsp_keep_alive = os.getenv("DO_RTSP_KEEP_ALIVE", "true").lower() in ("1", "true", "yes")


        # camera_id → SourceInfo
        self.sources: dict[int, SourceInfo] = {}

        # Reusable pool of streammux slot indices
        self._source_id_pool: list[int] = list(range(MAX_SOURCES))
        self._lock = threading.Lock()

        # Redis clients with retry logic for container networking
        self._redis = None
        self._redis_pub = None
        
        log.info("  📡 Connecting to Redis at %s:%d...", REDIS_HOST, REDIS_PORT)
        for attempt in range(5):
            try:
                self._redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)
                self._redis_pub = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
                self._redis.ping()
                log.info("  ✅ Connected to Redis")
                break
            except Exception as e:
                log.warning("  ⏳ Redis connect attempt %d failed: %s", attempt + 1, e)
                time.sleep(2)
        
        if not self._redis:
            log.error("  ❌ Could not connect to Redis after 5 attempts. Resolution failed.")

        # source_id → camera_id reverse map
        self._sid_to_camid: dict[int, int] = {}

        # Per-source frame counter for throttling JPEG capture
        self._frame_counters: dict[int, int] = {}

    # ------------------------------------------------------------------
    # Pipeline construction
    # ------------------------------------------------------------------
    def build_pipeline(self):
        """Construct the full pipeline (no sources attached yet)."""
        self.pipeline = Gst.Pipeline.new("headcount-pipeline")

        # --- Elements ---
        self.streammux = self._make_elem("nvstreammux", "streammux")
        self.streammux.set_property("batch-size", STREAMMUX_BATCH_SIZE)
        self.streammux.set_property("width", STREAMMUX_WIDTH)
        self.streammux.set_property("height", STREAMMUX_HEIGHT)
        self.streammux.set_property("batched-push-timeout", STREAMMUX_BATCHED_PUSH_TIMEOUT)
        self.streammux.set_property("live-source", 1)
        self.streammux.set_property("sync-inputs", 0) # CRITICAL: 0 prevents pipeline starvation from unsynchronized camera clocks
        self.streammux.set_property("enable-padding", 1) # Match AI aspect ratio expectations
        self.streammux.set_property("interpolation-method", 1) # Bilinear for low latency

        pgie = self._make_elem("nvinfer", "primary-gie")
        pgie.set_property("config-file-path", INFER_CONFIG)
        pgie.set_property("batch-size", STREAMMUX_BATCH_SIZE)

        tracker = self._make_elem("nvtracker", "tracker")
        tracker.set_property("tracker-width", 640)
        tracker.set_property("tracker-height", 640)
        tracker.set_property(
            "ll-lib-file",
            "/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so",
        )
        tracker.set_property("ll-config-file", TRACKER_CONFIG)

        # Tiler for matrix view - Updated to use high-res config
        self.tiler = self._make_elem("nvmultistreamtiler", "tiler")
        self.tiler.set_property("width", STREAMMUX_WIDTH)
        self.tiler.set_property("height", STREAMMUX_HEIGHT)
        self.tiler.set_property("interpolation-method", 1) # Bilinear
        self._update_tiler()

        nvvidconv = self._make_elem("nvvideoconvert", "convertor")
        nvvidconv.set_property("interpolation-method", 1) # Bilinear
        nvosd = self._make_elem("nvdsosd", "onscreendisplay")
        nvosd.set_property("process-mode", 1)  # GPU mode for sharper rendering

        nvvidconv2 = self._make_elem("nvvideoconvert", "convertor2")

        capsfilter = self._make_elem("capsfilter", "capsfilter")
        capsfilter.set_property(
            "caps",
            Gst.Caps.from_string("video/x-raw(memory:NVMM), format=NV12")
        )

        encoder = self._make_elem("nvv4l2h264enc", "encoder")
        encoder.set_property("bitrate", 4000000)       # Optimized 4 Mbps for monitoring
        encoder.set_property("preset-id", 4)           # UltraFast Preset for low latency
        encoder.set_property("profile", 2)             # Main Profile
        encoder.set_property("insert-sps-pps", True)
        encoder.set_property("idrinterval", 30) 
        
        # Direct Push Bridge -> MediaMTX
        # Modern rtspclientsink automatically handles RTP payloading internally.
        # Passing it an already-payloaded stream (rtph264pay) caused the previous caps conflict.
        # We pass the parsed H.264 stream directly to the sink.
        push_bin = Gst.parse_bin_from_description(
            "h264parse ! rtspclientsink location=rtsp://mediamtx:8554/stream protocols=tcp", 
            True 
        )

        # Added a queue for better stability (leaky to prevent blocking)
        queue = self._make_elem("queue", "queue_enc")
        queue.set_property("leaky", 2) # Drop oldest if full, keeps pipeline running
        queue.set_property("max-size-buffers", 30)
        
        # --- Add all to pipeline ---
        for elem in [
            self.streammux, pgie, tracker, self.tiler, nvvidconv,
            nvosd, nvvidconv2, capsfilter, queue, encoder, push_bin,
        ]:
            self.pipeline.add(elem)

        # --- Link chain ---
        assert self.streammux.link(pgie), "streammux → pgie link failed"
        assert pgie.link(tracker), "pgie → tracker link failed"
        assert tracker.link(self.tiler), "tracker → tiler link failed"
        
        assert self.tiler.link(nvvidconv), "tiler → nvvidconv link failed"
        assert nvvidconv.link(nvosd), "nvvidconv → nvosd link failed"
        assert nvosd.link(nvvidconv2), "nvosd → nvvidconv2 link failed"
        assert nvvidconv2.link(capsfilter), "nvvidconv2 → capsfilter link failed"
        assert capsfilter.link(queue), "capsfilter → queue link failed"
        assert queue.link(encoder), "queue → encoder link failed"
        assert encoder.link(push_bin), "encoder → push_bin link failed"

        # --- Probe on PGIE (AI Engine) src pad to extract metadata BEFORE tracker ---
        pgie_src_pad = pgie.get_static_pad("src")
        pgie_src_pad.add_probe(Gst.PadProbeType.BUFFER, self._buffer_probe, 0)

        # --- Metadata Probe (On Tracker src pad - sources are separate here) ---
        tracker_src_pad = tracker.get_static_pad("src")
        if tracker_src_pad:
            tracker_src_pad.add_probe(Gst.PadProbeType.BUFFER, self._tracker_probe, 0)

        # --- Snapshot Probe (On TILER src pad - always RGBA) ---
        tiler_src_pad = self.tiler.get_static_pad("src")
        if tiler_src_pad:
            tiler_src_pad.add_probe(Gst.PadProbeType.BUFFER, self._snapshot_probe, 0)

    def _setup_rtsp_server(self):
        """Deprecated: We now push directly to MediaMTX via rtspclientsink."""
        pass
        log.info("  ✅ RTSP Server ready at rtsp://0.0.0.0:8555/stream")


    # ------------------------------------------------------------------
    # GStreamer helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _make_elem(factory: str, name: str):
        """Create a GStreamer element or raise."""
        elem = Gst.ElementFactory.make(factory, name)
        if elem is None:
            raise RuntimeError(f"Failed to create GStreamer element: {factory} ({name})")
        return elem

    # ------------------------------------------------------------------
    # Probe callbacks — metadata extraction
    # ------------------------------------------------------------------
    def _buffer_probe(self, pad, info, _user_data):
        """
        Runs on every batch buffer produced by the PGIE (AI).
        Parses raw tensors and INJECTS metadata for the tracker.
        """
        gst_buffer = info.get_buffer()
        if not gst_buffer: return Gst.PadProbeReturn.OK

        batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
        l_frame = batch_meta.frame_meta_list
        while l_frame is not None:
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
            source_id = frame_meta.source_id
            camera_id = self._sid_to_camid.get(source_id, source_id)
            # --- Heartbeat Monitor ---
            # We no longer need to parse tensors in Python! 
            # The C++ Custom Parser (libnvdsinfer_custom_impl_Yolo.so) handles it all.
            if frame_meta.frame_num % 100 == 0:
                l_obj = frame_meta.obj_meta_list
                obj_count = 0
                while l_obj is not None:
                    obj_count += 1
                    l_obj = l_obj.next
                log.info("🎞️  Pipeline Heartbeat [Cam %d]: %d objects detected via C++ Parser", camera_id, obj_count)

            l_frame = l_frame.next
        return Gst.PadProbeReturn.OK

    def _tracker_probe(self, pad, info, _user_data):
        """
        Runs AFTER the tracker. Grabs the final Tracking IDs and sends to Redis.
        """
        gst_buffer = info.get_buffer()
        if not gst_buffer: return Gst.PadProbeReturn.OK

        batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
        l_frame = batch_meta.frame_meta_list
        while l_frame is not None:
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
            frame_num = frame_meta.frame_num
            source_id = frame_meta.source_id
            camera_id = self._sid_to_camid.get(source_id, source_id)
            
            tracker_ids = []
            xyxy_list = []
            conf_list = []

            l_obj = frame_meta.obj_meta_list
            while l_obj is not None:
                obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
                
                # Report tracked people (Class 0)
                if obj_meta.class_id == 0:
                    r = obj_meta.rect_params
                    # Official NvDCF Tracking ID!
                    tracker_ids.append(int(obj_meta.object_id))
                    xyxy_list.append([float(r.left), float(r.top), float(r.left+r.width), float(r.top+r.height)])
                    conf_list.append(float(obj_meta.confidence))
                
                l_obj = l_obj.next

            # --- Publish to Redis (The Tracker has now assigned persistent IDs!) ---
            si = self.sources.get(camera_id)
            if si:
                si.frame_count += 1
                
                # Update stable headcount
                si.count_history.append(len(tracker_ids))
                if len(si.count_history) > 20:
                    si.count_history.pop(0)
                if si.count_history:
                    si.stable_count = max(set(si.count_history), key=si.count_history.count)

                # Calculate FPS
                now = time.time()
                elapsed = now - si.last_fps_time
                if elapsed >= 1.0:
                    si.fps = int(si.frame_count / elapsed)
                    si.frame_count = 0
                    si.last_fps_time = now
                
                payload = json.dumps({
                    "tracker_ids": tracker_ids,
                    "xyxy": xyxy_list,
                    "conf": conf_list,
                    "count": si.stable_count,
                    "fps": si.fps,
                    "camera_id": camera_id,
                    "timestamp": now,
                })
                try:
                    self._redis_pub.publish(f"ds_data_{camera_id}", payload)
                except Exception as e:
                    print(f"❌ Redis Error: {e}")

            l_frame = l_frame.next
        return Gst.PadProbeReturn.OK

    def _snapshot_probe(self, pad, info, _user_data):
        """Extracts snapshots for all sources by cropping the tiled RGBA frame."""
        gst_buffer = info.get_buffer()
        if not gst_buffer: return Gst.PadProbeReturn.OK
        
        # Only snapshot every 30 frames to save CPU
        # We use a global counter since we are after the tiler (batch_size=1)
        if not hasattr(self, '_snap_counter'): self._snap_counter = 0
        self._snap_counter += 1
        if self._snap_counter % 30 != 0: return Gst.PadProbeReturn.OK

        try:
            # 1. Get the big tiled frame (RGBA)
            n_frame = pyds.get_nvds_buf_surface(hash(gst_buffer), 0)
            frame_copy = np.array(n_frame, copy=True, order='C')
            full_bgr = cv2.cvtColor(frame_copy, cv2.COLOR_RGBA2BGR)
            
            # 2. Determine grid layout (e.g. 2x2 for 3-4 sources)
            count = len(self.sources)
            cols = int(np.ceil(np.sqrt(count)))
            rows = int(np.ceil(count / cols))
            
            w = STREAMMUX_WIDTH // cols
            h = STREAMMUX_HEIGHT // rows
            
            # 3. Crop and save for each active camera
            for i, camera_id in enumerate(sorted(self.sources.keys())):
                r = i // cols
                c = i % cols
                
                crop = full_bgr[r*h:(r+1)*h, c*w:(c+1)*w]
                if crop.size > 0:
                    # Upscale crop back to logical 1080p resolution so zone coordinates match AI coordinates
                    crop_resized = cv2.resize(crop, (STREAMMUX_WIDTH, STREAMMUX_HEIGHT), interpolation=cv2.INTER_LINEAR)
                    _, buf = cv2.imencode('.jpg', crop_resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    self._redis.set(f"ds_frame:{camera_id}", buf.tobytes())
                    
        except Exception as e:
            print(f"❌ Snapshot Error: {e}")
            
        return Gst.PadProbeReturn.OK

    def _update_tiler(self):
        """Dynamically update tiler layout based on number of active paths.
        Using symmetric grids (1x1, 2x2, 3x3, 4x4) to preserve 16:9 aspect ratio.
        """
        count = len(self.sources)
        if count <= 1:
            rows, cols = 1, 1
        elif count <= 4:
            rows, cols = 2, 2
        elif count <= 9:
            rows, cols = 3, 3
        else:
            rows, cols = 4, 4

        if self.tiler:
            self.tiler.set_property("rows", rows)
            self.tiler.set_property("columns", cols)
            # Ensure it uses hardware scaling to avoid CPU bottlenecks
            self.tiler.set_property("compute-hw", 1)
            log.info("  🖼️  Tiler grid optimized to %dx%d (sources: %d)", rows, cols, count)

    # ------------------------------------------------------------------
    # Dynamic source management
    # ------------------------------------------------------------------
    def add_source(self, camera_id: int, url: str) -> bool:
        """Add an RTSP source to the running pipeline."""
        with self._lock:
            if camera_id in self.sources:
                log.info("Camera %d already exists, replacing...", camera_id)
                self._remove_source_locked(camera_id)

            if not self._source_id_pool:
                log.error("No source slots available (max %d)", MAX_SOURCES)
                return False

            source_id = self._source_id_pool.pop(0)
            source_bin = self._create_source_bin(source_id, url)
            if source_bin is None:
                self._source_id_pool.insert(0, source_id)
                return False

            self.pipeline.add(source_bin)

            # Re-use or Request streammux sink pad
            pad_name = f"sink_{source_id}"
            sinkpad = self.streammux.get_static_pad(pad_name)
            
            if not sinkpad:
                try:
                    sinkpad = self.streammux.request_pad_simple(pad_name)
                except Exception as e:
                    log.error("Error requesting streammux pad: %s", e)
                    sinkpad = None

            if sinkpad is None:
                log.error("Failed to get streammux pad %s", pad_name)
                self.pipeline.remove(source_bin)
                self._source_id_pool.insert(0, source_id)
                return False


            srcpad = source_bin.get_static_pad("src")
            # CRITICAL: We wait until uridecodebin emits a pad BEFORE dynamically linking to streammux.
            # Up-front linking here actively triggers a DeepStream memory segfault downstream.

            # Sync state with the running pipeline
            source_bin.sync_state_with_parent()

            info = SourceInfo(camera_id, url, source_id, source_bin)
            info.sinkpad = sinkpad
            info.is_live = True
            self.sources[camera_id] = info
            self._sid_to_camid[source_id] = camera_id

            # Update layout
            self._update_tiler()

            log.info(
                "✅ Source added: camera_id=%d  source_id=%d  url=%s",
                camera_id, source_id, url,
            )
            return True

    def remove_source(self, camera_id: int) -> bool:
        """Remove a source from the running pipeline."""
        with self._lock:
            return self._remove_source_locked(camera_id)

    def _remove_source_locked(self, camera_id: int) -> bool:
        """Internal remove (caller must hold self._lock)."""
        if camera_id not in self.sources:
            return False

        info = self.sources[camera_id]
        sid = info.source_id

        # --- Stabilized Removal ---
        src_pad = info.source_bin.get_static_pad("src")
        if src_pad and src_pad.is_linked():
            # Block data flow before unlinking to prevent memory corruption
            src_pad.add_probe(Gst.PadProbeType.BLOCK_DOWNSTREAM, lambda p, i, d: Gst.PadProbeReturn.OK, None)
            src_pad.unlink(info.sinkpad)
        
        # Note: We do NOT call release_request_pad here. 
        # Re-using the sink pad on streammux is much safer in DS 9.0.

        # NOW it is safe to shut down the source bin
        info.source_bin.set_state(Gst.State.NULL)
        self.pipeline.remove(info.source_bin)

        # Cleanup mappings
        self._sid_to_camid.pop(sid, None)
        del self.sources[camera_id]
        self._source_id_pool.append(sid)
        self._source_id_pool.sort()
        self._frame_counters.pop(sid, None)

        # Update layout
        self._update_tiler()

        # Clear stale Redis data
        try:
            self._redis.delete(f"ds_frame:{camera_id}")
        except Exception:
            pass

        log.info("🗑️  Source removed: camera_id=%d  source_id=%d", camera_id, sid)
        return True

    # ------------------------------------------------------------------
    # Source bin factory
    # ------------------------------------------------------------------
    def _create_source_bin(self, source_id: int, uri: str):
        """
        Create an nvurisrcbin for one RTSP/file source.
        nvurisrcbin is the specialized DeepStream source element.
        """
        bin_name = f"source-bin-{source_id:02d}"
        nbin = Gst.Bin.new(bin_name)

        # Standard uridecodebin effortlessly auto-plugs jpegdec (unlike nvurisrcbin)
        uri_decode_bin = Gst.ElementFactory.make("uridecodebin", f"uri-decode-{source_id}")
        
        if not uri_decode_bin:
            log.error("Failed to create uridecodebin")
            return None

        uri_decode_bin.set_property("uri", uri)
        
        # Configure internal rtspsrc for low latency and auto-reconnect
        uri_decode_bin.connect("source-setup", self._on_source_setup)

        
        # Handle decoded out pads natively
        uri_decode_bin.connect("pad-added", self._on_pad_added, nbin, source_id)

        nbin.add(uri_decode_bin)

        # -- Universal Hardware Memory Bridge --
        conv = Gst.ElementFactory.make("nvvideoconvert", f"conv-{source_id}")
        # Note: 'add-borders' or 'enable-padding' availability depends on DS version.
        # Removing to avoid TypeError. Aspect ratio is handled in nvinfer.
        
        caps = Gst.ElementFactory.make("capsfilter", f"caps-{source_id}")
        # Standardized to 1080p to match the streammux and tiler for maximum clarity
        caps.set_property("caps", Gst.Caps.from_string("video/x-raw(memory:NVMM), format=NV12, width=1920, height=1080"))
        
        nbin.add(conv)
        nbin.add(caps)
        conv.link(caps)

        # Ghost pad purely points to caps filter's guaranteed NV12 output
        ghost_pad = Gst.GhostPad.new("src", caps.get_static_pad("src"))
        ghost_pad.set_active(True)
        nbin.add_pad(ghost_pad)

        return nbin

    def _on_source_setup(self, bin, source):
        """Callback to configure the actual RTSP source element (rtspsrc)."""
        if Gst.Element.get_factory(source).get_name() == "rtspsrc":
            # Force TCP transport (0x4) — critical for stable streaming in Docker/WSL2
            # This eliminates "Could not read from resource" caused by UDP packet loss.
            source.set_property("protocols", 0x00000004)
            # Increase latency to 1.5s for maximum jitter tolerance
            source.set_property("latency", 1500)
            # Drop frames if they are too late to maintain real-time
            source.set_property("drop-on-latency", True)
            # Enable keep‑alive packets so NAT/routers keep the session open
            source.set_property("do-rtsp-keep-alive", self.do_rtsp_keep_alive)
            # Higher timeout (10s) to handle slow-starting camera sensors
            source.set_property("timeout", 10000000) 
            # Auto‑reconnect settings
            source.set_property("ntp-sync", True)

    def _on_pad_added(self, src, pad, source_bin, source_id):
        """Called when nvurisrcbin/uridecodebin produces a decoded audio/video pad."""
        caps = pad.get_current_caps()
        if not caps:
            caps = pad.query_caps(None)
        if not caps or caps.is_empty():
            return

        name = caps.get_structure(0).get_name()
        if "video" not in name:
            log.info("  🚫 Source %d: Ignored non-video pad (%s)", source_id, name)
            return

        conv = source_bin.get_by_name(f"conv-{source_id}")
        if not conv:
            log.error("  ❌ Source %d: critical failure, nvvideoconvert missing", source_id)
            return

        conv_sink = conv.get_static_pad("sink")

        # 1. First link downstream to streammux BEFORE connecting upstream
        # This ensures STREAM_START and SEGMENT events reach the streammux
        camera_id = self._sid_to_camid.get(source_id)
        if camera_id is not None and camera_id in self.sources:
            sinkpad = self.sources[camera_id].sinkpad
            ghost_pad = source_bin.get_static_pad("src")
            if ghost_pad and not ghost_pad.is_linked():
                try:
                    ret_mux = ghost_pad.link(sinkpad)
                    if ret_mux != Gst.PadLinkReturn.OK:
                        log.error("  ❌ Source %d: dynamically linked to streammux failed (ret=%s)", source_id, ret_mux)
                    else:
                        log.info("  🔗 Source %d: dynamically linked to streammux (ret=%s)", source_id, ret_mux)
                except Exception as e:
                    log.error("  ❌ Source %d: Exception on streammux link: %s", source_id, e)

        # 2. Then link the uridecodebin pad to conv
        if not conv_sink.is_linked():
            ret = pad.link(conv_sink)
            if ret != Gst.PadLinkReturn.OK:
                log.error("  ❌ Source %d: failed to natively link to hardware convert (ret=%s)", source_id, ret)
                return

        features = caps.get_features(0)
        mem_type = "NVMM" if features and features.contains("memory:NVMM") else "System"
        log.info("  ✅ Source %d: decoded video ready (%s, memory: %s) mapped to hardware bridge",
                 source_id, name, mem_type)

    # ------------------------------------------------------------------
    # Pipeline lifecycle
    # ------------------------------------------------------------------
    def start(self):
        """Build the pipeline, set to PLAYING, and run the GLib main loop."""
        if not self.pipeline:
            self.build_pipeline()
            self._setup_rtsp_server()

        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            log.error("Failed to set pipeline to PLAYING")
            return

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)

        self.loop = GLib.MainLoop()
        log.info("🚀 DeepStream pipeline is PLAYING — waiting for sources via REST API")

        try:
            self.loop.run()
        except KeyboardInterrupt:
            pass
        finally:
            self.pipeline.set_state(Gst.State.NULL)
            log.info("Pipeline stopped")

    def _on_bus_message(self, bus, msg):
        """Handle GStreamer bus messages — resilient to ONVIF metadata errors."""
        t = msg.type
        if t == Gst.MessageType.EOS:
            log.warning("End-of-stream received")
            self.loop.quit()
        elif t == Gst.MessageType.ERROR:
            err, debug = msg.parse_error()
            src_name = msg.src.get_name() if msg.src else "unknown"
            err_msg = err.message if err else "unknown error"

            # ONVIF metadata errors are harmless — ignore them completely
            # HOWEVER, we never ignore errors from the primary RTSP sink bridge
            harmless_patterns = [
                "No decoder available",
                "Could not read from resource",
            ]
            if any(p.lower() in err_msg.lower() for p in harmless_patterns) and "rtsp-sink" not in src_name:
                # Do NOT log a warning here anymore — just return silently to solve the noise
                return  # DO NOT propagate — let pipeline continue


            log.error("Error from %s: %s", src_name, err_msg)
            if debug:
                log.debug("  Debug: %s", debug)
            # Don't quit — other sources can keep running
        elif t == Gst.MessageType.WARNING:
            err, _ = msg.parse_warning()
            log.warning("Warning: %s", err.message)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def get_sources(self) -> list[dict]:
        """Return metadata for every active source."""
        with self._lock:
            return [
                {
                    "camera_id": si.camera_id,
                    "url": si.url,
                    "source_id": si.source_id,
                    "is_live": si.is_live,
                    "fps": si.fps,
                }
                for si in self.sources.values()
            ]


# ===========================================================================
# FastAPI REST API
# ===========================================================================
app = FastAPI(title="DeepStream Bridge API", version="1.0")
bridge = DeepStreamBridge()


class AddSourceRequest(BaseModel):
    camera_id: int
    url: str


@app.get("/api/v1/health")
def health():
    """Pipeline health check."""
    return {
        "status": "running",
        "active_sources": len(bridge.sources),
        "max_sources": MAX_SOURCES,
    }


@app.get("/api/v1/sources")
def list_sources():
    """List all active sources."""
    return bridge.get_sources()


@app.post("/api/v1/sources")
def add_source(req: AddSourceRequest):
    """Add a new RTSP source to the pipeline."""
    ok = bridge.add_source(req.camera_id, req.url)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to add source")
    return {"status": "added", "camera_id": req.camera_id}


@app.delete("/api/v1/sources/{camera_id}")
def remove_source(camera_id: int):
    """Remove a source from the pipeline."""
    ok = bridge.remove_source(camera_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"status": "removed", "camera_id": camera_id}


# ===========================================================================
# Entry point
# ===========================================================================
def main():
    log.info("=" * 60)
    log.info("  🧠 Headcount AI — DeepStream Bridge")
    log.info("  📡 REST API: http://0.0.0.0:%d", API_PORT)
    log.info("  📮 Redis:    %s:%d", REDIS_HOST, REDIS_PORT)
    log.info("  🎯 Max sources: %d  (batch-size: %d)", MAX_SOURCES, STREAMMUX_BATCH_SIZE)
    log.info("=" * 60)

    # Start FastAPI server in a daemon thread
    api_thread = threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"host": "0.0.0.0", "port": API_PORT, "log_level": "info"},
        daemon=True,
    )
    api_thread.start()

    # Run the DeepStream pipeline (blocks on GLib main loop)
    bridge.start()


if __name__ == "__main__":
    main()
