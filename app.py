"""Headcount AI Command Center — Entry Point

Usage:
    python app.py

Starts Flask server on port 5000 with:
    - Video processing thread (YOLO + BoT-SORT + AI Analytics)
    - Multi-camera management with area monitoring
    - REST API endpoints
    - React frontend (served from frontend/dist/)
"""
import os
import threading
import time
from flask import Flask, send_from_directory

from backend.memory import MemoryStore
from backend.ai_engine import AIAnalyticsEngine

from backend.camera_manager import CameraManager
from backend.area_monitor import AreaMonitor
from backend.routes.video import video_bp, init_video_routes
from backend.routes.stats import stats_bp, init_stats_routes
from backend.routes.zones import zones_bp, init_zones_routes
from backend.routes.audio import audio_bp, init_audio_routes
from backend.routes.cameras import cameras_bp, init_camera_routes

# ==============================================================================
# --- APP FACTORY ---
# ==============================================================================
app = Flask(__name__, static_folder='frontend/dist', static_url_path='')


# Manual CORS (allows React dev server on port 5173 to reach Flask on port 5000)
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    response.headers['Access-Control-Expose-Headers'] = 'X-Query-Text, X-Response-Text'
    return response

# --- Initialize Memory & AI Engine ---
memory = MemoryStore()
ai_engine = AIAnalyticsEngine(memory=memory)

# --- Initialize Multi-Camera System ---
camera_manager = CameraManager(memory, ai_engine=ai_engine)
area_monitor = AreaMonitor(ai_engine=ai_engine, memory=memory)

# Inject camera manager back into AI engine for live stats access
ai_engine.camera_manager = camera_manager

# --- Register Blueprints ---
app.register_blueprint(video_bp)
app.register_blueprint(stats_bp)
app.register_blueprint(zones_bp)
app.register_blueprint(audio_bp)
app.register_blueprint(cameras_bp)

# --- Inject dependencies into routes ---
init_stats_routes(ai_engine, camera_manager.get_aggregated_stats, camera_manager.reset_all_stats, memory)
init_audio_routes(ai_engine)
init_camera_routes(memory, camera_manager, area_monitor)
init_video_routes(camera_manager)
init_zones_routes(camera_manager)

# --- Serve static assets (logo etc.) ---
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')


@app.route('/api/ping')
def ping_api():
    return jsonify({"status": "alive", "server": "Headcount AI"})


@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)


# --- Serve React app (production build) ---
@app.route('/')
def serve_react():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def serve_react_assets(path):
    """Serve React build assets, fallback to index.html for SPA routing."""
    file_path = os.path.join(app.static_folder, path)
    if os.path.exists(file_path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')


# ==============================================================================
# --- AREA MONITOR SYNC THREAD ---
# ==============================================================================
def _area_sync_loop():
    """Periodically feeds area stats from camera_manager into area_monitor."""
    while True:
        time.sleep(10)
        try:
            area_stats = camera_manager.get_area_stats()
            for area_name, stats in area_stats.items():
                area_monitor.update_area(area_name, stats["people_count"])
        except Exception as e:
            print(f"  ⚠️ Area sync error: {e}")


# ==============================================================================
# --- START ---
# ==============================================================================
if __name__ == '__main__':
    print("=" * 60)
    print("  🧠 Headcount AI Command Center")
    print("  💾 Memory: SQLite persistence enabled")
    print("  📹 Multi-Camera: Enabled")
    print("=" * 60)

    # Start multi-camera system in background to avoid blocking the API server
    print("  Loading saved cameras (background)...")
    threading.Thread(target=camera_manager.load_and_start_all, daemon=True).start()

    # Start area monitor sync
    sync_thread = threading.Thread(target=_area_sync_loop, daemon=True)
    sync_thread.start()

    print("  🌐 Server running at http://localhost:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)


