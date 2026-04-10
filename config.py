"""Centralized configuration for the Headcount AI system."""
import json
import os
import numpy as np
import threading

# ==============================================================================
# --- CAMERA & MODEL ---
# ==============================================================================

MODEL_PATH = 'yolo26l.pt'
POSE_MODEL_PATH = 'yolo26l-pose.pt'

# Tracker config (local file with ReID enabled)
TRACKER_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'botsort_reid.yaml')

# Target FPS for video streaming to frontend
TARGET_STREAM_FPS = 24

# ==============================================================================
# --- SAFETY ---
# ==============================================================================
SAFETY_LIMIT = 10

# ==============================================================================
# --- DETECTION ---
# ==============================================================================
CONFIDENCE_THRESHOLD = 0.45  # Lowered back to allow detection of partially occluded seated people
IOU_THRESHOLD = 0.45
ENTRY_DEBOUNCE_SEC = 0.5
ENTRY_MIN_CONFIDENCE = 0.60  # Require decent confidence to log an entry
GHOST_TIMEOUT_SEC = 3        # Clear ghosts faster

# ==============================================================================
# --- EMAIL ALERTS ---
# ==============================================================================
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
ALERT_RECIPIENTS = [r.strip() for r in os.environ.get('ALERT_RECIPIENTS', '').split(',') if r.strip()]
ALERT_COOLDOWN_MINUTES = 60  # Don't re-send same alert within this window
MISSING_ALERT_WINDOW_MINUTES = 60  # How long count must stay below limit to trigger alert

# ==============================================================================
# --- AREA LIMITS ---
# ==============================================================================
DEFAULT_AREA_PEOPLE_LIMIT = 0  # 0 means no limit set

# ==============================================================================
# --- COLORS (BGR) ---
# ==============================================================================
COLOR_ZONE_A = (0, 0, 255)       # Red — Outside/Danger
COLOR_ZONE_B = (0, 255, 0)       # Green — Inside/Safe
COLOR_BOX = (0, 255, 255)        # Yellow
COLOR_SKELETON = (255, 0, 0)     # Blue
COLOR_KEYPOINTS = (255, 255, 255) # White

# ==============================================================================
# --- ZONE MANAGEMENT ---
# ==============================================================================
ZONES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zones.json')
_zones_lock = threading.Lock()
_zones_version = 0  # Incremented on every save for change detection

# Default zones (used if zones.json doesn't exist)
DEFAULT_ZONES = {
    "zone_a": [
        [818, 333], [737, 386], [733, 394],
        [715, 404], [722, 436], [866, 342]
    ],
    "zone_b": [
        [883, 192], [895, 324], [871, 341],
        [723, 438], [496, 612], [347, 730],
        [319, 700], [142, 866], [279, 1034],
        [1321, 1031], [1422, 656], [1459, 430],
        [1485, 275], [1195, 224]
    ]
}


def load_zones():
    """Load zone polygons from zones.json, or return defaults."""
    with _zones_lock:
        if os.path.exists(ZONES_FILE):
            try:
                with open(ZONES_FILE, 'r') as f:
                    data = json.load(f)
                return {
                    "zone_a": np.array(data.get("zone_a", DEFAULT_ZONES["zone_a"])),
                    "zone_b": np.array(data.get("zone_b", DEFAULT_ZONES["zone_b"]))
                }
            except (json.JSONDecodeError, Exception) as e:
                print(f"⚠️ Error loading zones.json: {e}. Using defaults.")

        return {
            "zone_a": np.array(DEFAULT_ZONES["zone_a"]),
            "zone_b": np.array(DEFAULT_ZONES["zone_b"])
        }


def save_zones(zone_a_list, zone_b_list):
    """Save zone polygons to zones.json and bump version."""
    global _zones_version
    with _zones_lock:
        data = {"zone_a": zone_a_list, "zone_b": zone_b_list}
        with open(ZONES_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        _zones_version += 1
        print(f"✅ Zones saved (version {_zones_version})")
    return _zones_version


def get_zones_version():
    """Get current zone config version number."""
    return _zones_version


def get_zones_raw():
    """Get zones as plain lists (for JSON API responses)."""
    with _zones_lock:
        if os.path.exists(ZONES_FILE):
            try:
                with open(ZONES_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return DEFAULT_ZONES
