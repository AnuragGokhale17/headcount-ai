"""Configuration constants for the DeepStream Bridge Application.

These values are used by ds_app.py inside the Docker container.
Adjust MAX_SOURCES and STREAMMUX_BATCH_SIZE to scale beyond the PoC.
"""

import os

# --- Redis ---
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# --- REST API ---
API_PORT = 8010

# --- Pipeline Scaling ---
MAX_SOURCES = 100              # Stable scaling for RTX 5090
STREAMMUX_BATCH_SIZE = 3       # Match the actual number of sources for perfect synchronization
 
# --- Inference ---
INFER_CONFIG = "/workspace/deepstream/config_infer_yolo.txt"
TRACKER_CONFIG = "/workspace/deepstream/nvdcf_refined.yml"
 
# --- Streammux ---
STREAMMUX_WIDTH = 1920        # Increased to 1080p for higher quality tiled RTSP output
STREAMMUX_HEIGHT = 1080
STREAMMUX_BATCHED_PUSH_TIMEOUT = 33000  # 33ms (30fps) for perfectly smooth video playback

# --- Frame Publishing ---
FRAME_PUBLISH_INTERVAL = 4    # Balanced publishing rate
JPEG_QUALITY = 70             # Balanced quality/bandwidth for 10 streams
FRAME_TTL_SECONDS = 2         # Redis key expiry for stale frames
