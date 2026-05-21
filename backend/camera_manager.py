"""Multi-Camera Manager — Manages concurrent video processing threads.

Each camera runs the SAME full tracking pipeline as the primary camera:
zone-based counting, entry/exit detection, debouncing, ghost cleanup,
face recognition, and AI engine updates.
"""
import threading
import time
import os
import json
import cv2
import numpy as np
import supervision as sv
from collections import defaultdict
import requests
import config
import redis
import re
from .spatial_merger import SpatialMerger

# DeepStream Bridge API (runs inside Docker container on WSL2)
# _raw_ds_api = os.environ.get("DS_API_BASE", "127.0.0.1:8010")
# Robustly get the environment variable

# def _clean_url(url):
#     # Remove protocol if there
#     url = url.replace("http://", "").replace("https://", "")
#     # Remove all whitespace and common mangled characters
#     url = "".join(c for c in url if c.isalnum() or c == "." or c == ":")
#     # Fix double-colons
#     while "::" in url:
#         url = url.replace("::", ":")
#     # Ensure it starts with http://
#     return f"http://{url.strip(':')}"

# FINAL_DS_API_URL = _clean_url(_raw_ds_api)
# print(f"  🔧 CameraManager: Using DeepStream API at {FINAL_DS_API_URL}")

# --- CLEAN URL LOGIC ---
_raw_ds_api = os.environ.get("DS_API_BASE")

# If it's None OR an empty string, use the Docker service name
if not _raw_ds_api:
    _raw_ds_api = "deepstream:8010"

# Basic cleaning to ensure no whitespace or protocol double-up
_raw_ds_api = _raw_ds_api.replace("http://", "").replace("https://", "").strip()
FINAL_DS_API_URL = f"http://{_raw_ds_api}"

print(f"  🔧 CameraManager: Using DeepStream API at {FINAL_DS_API_URL}")



class CameraProcessor:
    """Processes a single RTSP stream with the full tracking pipeline."""

    def __init__(self, camera_id, name, url, area="default", plant="Plant 1", ai_engine=None, memory=None):
        self.camera_id = camera_id
        self.name = name
        self.url = url
        self.area = area
        self.plant = plant
        self.ai_engine = ai_engine
        self.memory = memory

        self.people_in_count = 0
        self.people_out_count = 0

        # Per-camera stats (mirrors global_stats in video_processor)
        self.stats = {
            "in": 0,
            "out": 0,
            "occupancy": 0,
            "total_detected": 0,
            "fps": 0,
        }
        # Spatial Heatmap Grid (32x18 resolution for 16:9 streams)
        self.heatmap = np.zeros((18, 32), dtype=np.float32)
        self.last_decay_time = time.time()
        self.is_running = False
        self.is_connected = False
        self.last_error = None
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Frame output for streaming
        self.output_frame = None
        self.frame_lock = threading.Lock()
        self._encoded_frame = None  # Pre-encoded JPEG bytes for snapshot serving
        
        self._zones_changed = threading.Event()
        self._zones_changed.set()

        self._latest_cap_frame = None
        self._cap_lock = threading.Lock()
        self._wants_reset = False

        # Internal state/objects (initialized in _process_loop but declared here for safety)
        self.zone_a_poly = None
        self.zone_b_poly = None
        self.zone_annotator_a = None
        self.zone_annotator_b = None
        self.box_annotator = None
        self.label_annotator = None
        self.latest_detections = None
        self.latest_labels = []

    def get_encoded_frame(self):
        """Return the latest JPEG bytes for snapshots."""
        with self.frame_lock:
            return self._encoded_frame

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()
        print(f"  📹 Camera '{self.name}' ({self.area}) started → {self.url}")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        self.is_running = False
        self.is_connected = False
        print(f"  ⏹️ Camera '{self.name}' stopped")

    def reload_zones(self):
        self._zones_changed.set()

    def _load_counters(self):
        self.people_in_count = 0
        self.people_out_count = 0
        if self.memory:
            self.people_in_count = self.memory.load_state(f"cam_{self.camera_id}_in", 0)
            self.people_out_count = self.memory.load_state(f"cam_{self.camera_id}_out", 0)

    def _save_counters(self):
        if self.memory:
            self.memory.save_all_state({
                f"cam_{self.camera_id}_in": self.people_in_count,
                f"cam_{self.camera_id}_out": self.people_out_count
            })

    def reset_stats(self):
        """Reset the IN and OUT counters to zero."""
        with self._lock:
            self.people_in_count = 0
            self.people_out_count = 0
            self._wants_reset = True
        self._save_counters()

    def get_stats(self):
        with self._lock:
            return {
                "camera_id": self.camera_id,
                "name": self.name,
                "area": self.area,
                "plant": self.plant,
                "people_count": self.stats["occupancy"],
                "total_detected": self.stats.get("total_detected", 0),
                "in": self.people_in_count,
                "out": self.people_out_count,
                "fps": self.stats["fps"],
                "is_running": self.is_running,
                "is_connected": self.is_connected,
                "last_error": self.last_error,
            }

    def get_current_detections(self):
        """Returns detections for spatial merging: list of {'x': x, 'y': y, 'id': tid}"""
        with self._cap_lock:
            if self.latest_detections is None or self.latest_detections.xyxy is None:
                return []
            
            dets = []
            for i, box in enumerate(self.latest_detections.xyxy):
                tid = int(self.latest_detections.tracker_id[i]) if self.latest_detections.tracker_id is not None else 0
                # Use bottom-center (feet) for homography
                x_c = (box[0] + box[2]) / 2
                y_c = box[3]
                dets.append({'camera_id': self.camera_id, 'x': x_c, 'y': y_c, 'id': tid})
            return dets

    def _process_loop(self):
        """
        Optimized Logic Engine: Listens to DeepStream via Redis.
        Maintains your original counting, debouncing, and ghost cleanup logic.
        """
        self.is_running = True
        self.is_connected = True # Connection is managed by DeepStream

        # 1. Initialize Redis Connection
        try:
            # Cleanly parse REDIS_HOST (handle multiple IPs/whitespaces/colons)
            raw_host = os.environ.get("REDIS_HOST", "127.0.0.1")
            redis_host = raw_host.replace(":", "").split()[0]
            redis_port = int(os.environ.get("REDIS_PORT", "6379"))
            
            r = redis.Redis(host=redis_host, port=redis_port, socket_connect_timeout=2, decode_responses=True)
            pubsub = r.pubsub()
            pubsub.subscribe(f"ds_data_{self.camera_id}")
            print(f"  🧠 [{self.name}] Logic Engine linked to Redis at {redis_host}:{redis_port}")
        except Exception as e:
            self.last_error = f"Redis connection failed to {redis_host}: {e}"
            print(f"  ⚠️ [{self.name}] {self.last_error}")
            self.is_running = False
            return

        # 2. Initialize Internal Tracking State (Your Original Logic)
        person_history = defaultdict(list)
        last_seen = {}
        entry_time = {}
        counted_in_ids = set()
        last_persist_time = time.time()
        
        # Temporal smoothing for occupancy
        self.occupancy_history = []
        
        # Local zone objects (re-initialized on change)
        zone_a = zone_b = None

        # Restore counters from SQLite/Memory
        self._load_counters()

        # 3. Data Processing Loop
        for message in pubsub.listen():
            if self._stop_event.is_set():
                break
            if message['type'] != 'message':
                continue

            # A. Parse data from DeepStream
            try:
                payload = json.loads(message['data'])
                # Expected payload: {"tracker_ids": [], "xyxy": [], "conf": [], "fps": 24}
                
                if not payload.get('tracker_ids'):
                    detections = sv.Detections.empty()
                    self.stats['total_detected'] = 0
                else:
                    # Map DeepStream data to Supervision format
                    detections = sv.Detections(
                        xyxy=np.array(payload['xyxy']),
                        confidence=np.array(payload['conf']),
                        class_id=np.array([0] * len(payload['tracker_ids'])),
                        tracker_id=np.array(payload['tracker_ids'])
                    )
                    # Raw count is always the length of detections
                    self.stats['total_detected'] = len(payload['tracker_ids'])
            except Exception as e:
                print(f"  ⚠️ [{self.name}] Data parse error: {e}")
                continue

            curr_time = time.time()
            
            # --- UPDATE OCCUPANCY ---
            # If DeepStream provides a 'stable_count' (which it does in ds_app.py), use it.
            # Otherwise, use the number of people currently tracked in Zone B.
            ds_stable_count = payload.get('count')
            
            # B. Check for Zone Config Changes (Your Original Logic)
            if self._zones_changed.is_set() or zone_a is None:
                self._zones_changed.clear()
                # (Load polygons from memory/config as per your original logic)
                cam = self.memory.get_camera(self.camera_id) if self.memory else None
                za_raw = json.loads(cam.get("zone_a") or "null") if cam else None
                zb_raw = json.loads(cam.get("zone_b") or "null") if cam else None
                
                if not za_raw or not zb_raw:
                    defaults = config.get_zones_raw()
                    za_raw = za_raw or defaults.get("zone_a", [])
                    zb_raw = zb_raw or defaults.get("zone_b", [])

                self.zone_a_poly = np.array(za_raw, dtype=np.int32)
                self.zone_b_poly = np.array(zb_raw, dtype=np.int32)
                
                zone_a = sv.PolygonZone(polygon=self.zone_a_poly, triggering_anchors=[sv.Position.CENTER])
                zone_b = sv.PolygonZone(polygon=self.zone_b_poly, triggering_anchors=[sv.Position.CENTER])

            # C. Update Tracking Timestamps (Your Original Logic)
            if detections.tracker_id is not None:
                for tid in detections.tracker_id:
                    last_seen[int(tid)] = curr_time

            # D. Spatial Filtering (Zones)
            in_zone_a = zone_a.trigger(detections=detections)
            in_zone_b = zone_b.trigger(detections=detections)

            # E. Core Counting Logic (Your Original Logic)
            if detections.tracker_id is not None:
                for i, tracker_id_raw in enumerate(detections.tracker_id):
                    tracker_id = int(tracker_id_raw)
                    history = person_history[tracker_id]
                    conf = detections.confidence[i]

                    current_zone = 'A' if in_zone_a[i] else ('B' if in_zone_b[i] else None)

                    # Update path history
                    if current_zone and (not history or history[-1] != current_zone):
                        history.append(current_zone)
                        if len(history) > 5: history.pop(0)

                    # --- ENTRY LOGIC ---
                    if tracker_id not in counted_in_ids:
                        if current_zone == 'B':
                            if conf > config.ENTRY_MIN_CONFIDENCE:
                                if tracker_id not in entry_time:
                                    entry_time[tracker_id] = curr_time
                                elif (curr_time - entry_time[tracker_id]) >= config.ENTRY_DEBOUNCE_SEC:
                                    self.people_in_count += 1
                                    counted_in_ids.add(tracker_id)
                                    if self.ai_engine:
                                        self.ai_engine.log_entry(tracker_id, curr_time)
                                    print(f"✅ [{self.name}] ENTRY: Person #{tracker_id}")
                        elif current_zone == 'A':
                            if tracker_id in entry_time:
                                del entry_time[tracker_id]

                    # --- EXIT LOGIC ---
                    if len(history) >= 2 and history[-2:] == ['B', 'A']:
                        if tracker_id in counted_in_ids:
                            self.people_out_count += 1
                            counted_in_ids.discard(tracker_id)
                            if self.ai_engine:
                                self.ai_engine.log_exit(tracker_id, reason="transition")
                            print(f"🚪 [{self.name}] EXIT: Person #{tracker_id}")
                        person_history[tracker_id] = ['A', 'A']

            # F. Ghost Cleanup (Your Original Logic)
            for tid in list(counted_in_ids):
                if tid not in last_seen or (curr_time - last_seen[tid]) > 15:
                    counted_in_ids.discard(tid)
                    if tid in entry_time: del entry_time[tid]
                    self.people_out_count += 1 # Auto-exit ghosts
                    if self.ai_engine:
                        self.ai_engine.log_exit(tid, reason="timeout")
                    print(f"👻 [{self.name}] CLEANUP: Ghost #{tid}")

            # G. Update Heatmap Data
            if detections.xyxy is not None:
                for box in detections.xyxy:
                    # Use bottom-center for more accurate spatial placement
                    x_c = (box[0] + box[2]) / 2
                    y_c = box[3] # Feet position
                    
                    # Map to 32x18 grid (assumes 1920x1080 source)
                    gx = int(x_c * 32 / 1920)
                    gy = int(y_c * 18 / 1080)
                    
                    if 0 <= gx < 32 and 0 <= gy < 18:
                        self.heatmap[gy, gx] += 1.0

            # Periodic Decay (keeps heatmap relevant to recent activity)
            if (curr_time - self.last_decay_time) > 5.0:
                self.heatmap *= 0.95 # Decay by 5% every 5 seconds
                self.last_decay_time = curr_time

            # H. Update AI Engine & Local Stats (Your Original Logic)
            if self.ai_engine:
                self.ai_engine.update(detections, in_zone_a, in_zone_b, counted_in_ids, 
                                      self.people_in_count, self.people_out_count, curr_time)

            with self._lock:
                self.stats['in'] = self.people_in_count
                self.stats['out'] = self.people_out_count
                
                # Use DeepStream's stable count if available, otherwise use our tracked set
                target_occ = ds_stable_count if ds_stable_count is not None else len(counted_in_ids)
                
                # --- Jitter Smoothing ---
                self.occupancy_history.append(target_occ)
                if len(self.occupancy_history) > 10: # Faster response (0.5s at 20fps)
                    self.occupancy_history.pop(0)
                
                if self.occupancy_history:
                    # Statistical Mode (most frequent count in window)
                    stable_occ = max(set(self.occupancy_history), key=self.occupancy_history.count)
                    self.stats['occupancy'] = stable_occ
                else:
                    self.stats['occupancy'] = target_occ
                    
                self.stats['fps'] = payload.get('fps', 0)

            # Snapshot for UI (using the detections we just received)
            with self._cap_lock:
                self.latest_detections = detections

            # Periodically persist to SQLite
            if self.memory and (curr_time - last_persist_time) > 30:
                last_persist_time = curr_time
                self._save_counters()

        self.is_running = False
        self.is_connected = False


class CameraManager:
    """Manages multiple CameraProcessor instances and aggregates area stats."""

    def __init__(self, memory, ai_engine=None):
        self.memory = memory
        self.ai_engine = ai_engine
        self._processors = {}  # camera_id -> CameraProcessor
        self.merger = SpatialMerger()
        self._lock = threading.Lock()

        # Redis connection for reading DeepStream-published frames
        try:
            # Cleanly parse REDIS_HOST
            raw_host = os.environ.get("REDIS_HOST", "127.0.0.1")
            redis_host = raw_host.replace(":", "").split()[0]
            redis_port = int(os.environ.get("REDIS_PORT", "6379"))
            
            print(f"  📮 CameraManager: Attempting to connect to Redis at {redis_host}:{redis_port}...")
            self._redis = redis.Redis(host=redis_host, port=redis_port, socket_connect_timeout=2, decode_responses=False)
            self._redis.ping()
            print(f"  ✅ CameraManager: Redis connected to {redis_host}")
        except Exception as e:
            print(f"  ⚠️ CameraManager: Redis connection failed to {redis_host}:6379 ({e})")
            self._redis = None

    def load_and_start_all(self):
        cameras = self.memory.get_cameras(active_only=True)
        for cam in cameras:
            # Update merger with existing homography
            if cam.get("homography_matrix"):
                try:
                    self.merger.update_camera_homography(cam["id"], json.loads(cam["homography_matrix"]))
                except: pass
            self.start_camera(cam["id"], cam["name"], cam["url"], cam["area"], cam.get("plant", "Plant 1"))
        print(f"  📡 CameraManager: {len(cameras)} camera(s) loaded and started")

    # def start_camera(self, camera_id, name, url, area="default", plant="Plant 1"):
    #     with self._lock:
    #         if camera_id in self._processors:
    #             self._processors[camera_id].stop()
            
    #         proc = CameraProcessor(
    #             camera_id=camera_id,
    #             name=name,
    #             url=url,
    #             area=area,
    #             plant=plant,
    #             memory=self.memory,
    def _get_clean_api_url(self):
        """Returns the pre-validated FINAL_DS_API_URL defined at the top."""
        return FINAL_DS_API_URL

    def restart_camera(self, camera_id):
        """Restarts a camera by stopping and starting it."""
        cam = self.memory.get_camera(camera_id)
        if not cam:
            return False, "Camera not found in database"
        
        print(f"  🔄 Restarting camera {camera_id} ({cam['name']})...")
        self.stop_camera(camera_id)
        return self.start_camera(camera_id, cam["name"], cam["url"], cam["area"], cam.get("plant", "Plant 1"))

    def start_camera(self, camera_id, name, url, area="default", plant="Plant 1"):
        """Syncs the camera with DeepStream and starts the local logic engine."""
        clean_api = self._get_clean_api_url()
        sync_success = True
        error_msg = None
        
        # Auto-correct local file paths for DeepStream
        if url.startswith("/workspace") and not url.startswith("file://"):
            url = f"file://{url}"
            print(f"  📝 [Bridge] Auto-formatted local path: {url}")

        with self._lock:
            # 1. Tell DeepStream Bridge to add this RTSP source
            try:
                print(f"  📡 [Sync] Sending {camera_id} to bridge at {clean_api}...")
                resp = requests.post(
                    f"{clean_api}/api/v1/sources",
                    json={"camera_id": camera_id, "url": url},
                    timeout=4,
                )
                if resp.ok:
                    print(f"  🔗 DeepStream: source {camera_id} added")
                else:
                    sync_success = False
                    error_msg = f"DeepStream error ({resp.status_code}): {resp.text}"
                    print(f"  ⚠️ {error_msg}")
            except requests.ConnectionError:
                sync_success = False
                error_msg = f"DeepStream bridge not reachable at {clean_api}"
                print(f"  ⚠️ {error_msg}")
            except Exception as e:
                sync_success = False
                error_msg = f"DeepStream sync error: {e}"
                print(f"  ⚠️ {error_msg}")

            # 2. Start the local logic processor (Redis listener for counting)
            if camera_id in self._processors:
                self._processors[camera_id].stop()
            
            proc = CameraProcessor(
                camera_id=camera_id,
                name=name,
                url=url,
                area=area,
                plant=plant,
                memory=self.memory,
                ai_engine=self.ai_engine
            )
            proc.start()
            self._processors[camera_id] = proc
            
        return sync_success, error_msg

    def stop_camera(self, camera_id):
        with self._lock:
            # Remove from DeepStream pipeline
            try:
                requests.delete(
                    f"{FINAL_DS_API_URL}/api/v1/sources/{camera_id}",
                    timeout=5,
                )
                print(f"  🗑️ DeepStream: source {camera_id} removed")
            except Exception as e:
                print(f"  ⚠️ DeepStream remove error: {e}")

            if camera_id in self._processors:
                self._processors[camera_id].stop()
                del self._processors[camera_id]

    def stop_all(self):
        with self._lock:
            for proc in self._processors.values():
                proc.stop()
            self._processors.clear()

    def get_all_stats(self):
        with self._lock:
            return [proc.get_stats() for proc in self._processors.values()]

    def reset_all_stats(self):
        """Reset IN/OUT stats for all active cameras."""
        print("🧹 [CameraManager] Resetting all stats...")
        with self._lock:
            for proc in self._processors.values():
                proc.reset_stats()
        
        if self.ai_engine:
            self.ai_engine.reset()
        print("✅ [CameraManager] All stats reset successfully")

    def get_aggregated_stats(self):
        """Aggregate stats across all cameras, replacing the old global_stats."""
        total_in = 0
        total_out = 0
        total_occupancy = 0
        avg_fps = 0
        active_count = 0
        
        with self._lock:
            for proc in self._processors.values():
                stats = proc.get_stats()
                total_in += stats.get("in", 0)
                total_out += stats.get("out", 0)
                total_occupancy += stats.get("people_count", 0)
                if stats.get("is_connected"):
                    avg_fps += stats.get("fps", 0)
                    active_count += 1
                    
        if active_count > 0:
            avg_fps = int(avg_fps / active_count)
            
        # --- NEW SPATIAL DEDUPLICATION ---
        all_dets = []
        with self._lock:
            for proc in self._processors.values():
                all_dets.extend(proc.get_current_detections())
        
        # If no homography matrices are set, fallback to simple sum
        if not self.merger.cameras_homography:
            total_occupancy = total_occupancy
        else:
            total_occupancy = self.merger.get_unique_count(all_dets)

        return {
            "in": total_in,
            "out": total_out,
            "occupancy": total_occupancy,
            "fps": avg_fps
        }

    def get_area_stats(self):
        area_counts = defaultdict(lambda: {"people_count": 0, "cameras": 0, "connected": 0})
        with self._lock:
            for proc in self._processors.values():
                stats = proc.get_stats()
                area = stats["area"]
                area_counts[area]["people_count"] += stats["people_count"]
                area_counts[area]["cameras"] += 1
                if stats["is_connected"]:
                    area_counts[area]["connected"] += 1
        return dict(area_counts)

    def get_plant_stats(self):
        plant_counts = defaultdict(lambda: {"people_count": 0, "cameras": 0, "connected": 0})
        with self._lock:
            for proc in self._processors.values():
                stats = proc.get_stats()
                plant = stats.get("plant", "Plant 1")
                plant_counts[plant]["people_count"] += stats["people_count"]
                plant_counts[plant]["cameras"] += 1
                if stats["is_connected"]:
                    plant_counts[plant]["connected"] += 1
        return dict(plant_counts)

    def _get_redis_client(self):
        """Lazy-initialize a reliable Redis client."""
        if hasattr(self, '_redis') and self._redis:
            return self._redis
        
        try:
            raw_host = os.environ.get("REDIS_HOST", "redis")
            # Robustly split host and port
            if ":" in raw_host:
                parts = raw_host.split(":")
                redis_host = parts[0].strip()
                redis_port = int(parts[1].strip())
            else:
                redis_host = raw_host.strip()
                redis_port = int(os.environ.get("REDIS_PORT", "6379"))

            self._redis = redis.Redis(
                host=redis_host, 
                port=redis_port, 
                socket_connect_timeout=2, 
                decode_responses=False
            )
            self._redis.ping()
            return self._redis
        except Exception as e:
            print(f"  ⚠️ CameraManager: Redis link failed ({redis_host}:{redis_port}): {e}")
            self._redis = None
            return None

    def get_camera_frame(self, camera_id):
        """Read the latest annotated JPEG frame with triple-redundancy."""
        r = self._get_redis_client()
        
        # --- 1. TRY REDIS (DeepStream Output) ---
        if r:
            try:
                frame_data = r.get(f"ds_frame:{camera_id}")
                if frame_data:
                    return frame_data
                
                # Fuzzy match for index shifts
                keys = r.keys("ds_frame:*")
                if keys:
                    return r.get(keys[0])
            except Exception:
                pass

        # --- 2. TRY INTERNAL PROCESSOR BUFFER (Live Frame) ---
        # This is the fastest fallback and highly reliable
        proc = None
        with self._lock:
            proc = self._processors.get(camera_id)
        
        if proc:
            with proc.frame_lock:
                if proc._encoded_frame:
                    return proc._encoded_frame

        # --- 3. TRY DIRECT RTSP (OpenCV) ---
        # Only if the first two failed and we have a URL
        if proc and proc.url:
            now = time.time()
            if not hasattr(self, '_fallback_cache'): self._fallback_cache = {}
            
            cached_time, cached_frame = self._fallback_cache.get(camera_id, (0, None))
            if now - cached_time < 3.0: # 3 second cache
                return cached_frame

            try:
                # Use a non-blocking subprocess or very short timeout
                cap = cv2.VideoCapture(proc.url)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 1500)
                if cap.isOpened():
                    ret, frame = cap.read()
                    cap.release()
                    if ret:
                        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        frame_bytes = buffer.tobytes()
                        self._fallback_cache[camera_id] = (now, frame_bytes)
                        return frame_bytes
            except Exception as e:
                print(f"  ⚠️ CameraManager: Direct grab fallback failed for {camera_id}: {e}")

        return None

    def get_camera_heatmap(self, camera_id):
        """Retrieve the 32x18 heatmap grid for a specific camera."""
        with self._lock:
            proc = self._processors.get(camera_id)
            if proc:
                return proc.heatmap.tolist()
        return None

    def get_processor(self, camera_id):
        with self._lock:
            return self._processors.get(camera_id)
