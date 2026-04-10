"""Camera management API routes.

Endpoints:
    GET    /api/cameras         — List all cameras
    POST   /api/cameras         — Add a new camera
    PUT    /api/cameras/<id>    — Update a camera
    DELETE /api/cameras/<id>    — Remove a camera
    GET    /api/cameras/<id>/feed — MJPEG stream for a camera
    GET    /api/areas           — Aggregated area stats
    GET    /api/area_alerts     — Activity reduction alerts
    GET    /api/area_status     — Current monitoring status
"""
from flask import Blueprint, jsonify, request, Response
import time

cameras_bp = Blueprint('cameras', __name__)

_memory = None
_camera_manager = None
_area_monitor = None


def init_camera_routes(memory, camera_manager, area_monitor):
    global _memory, _camera_manager, _area_monitor
    _memory = memory
    _camera_manager = camera_manager
    _area_monitor = area_monitor


# =========================================================================
# CAMERA CRUD
# =========================================================================

@cameras_bp.route("/api/cameras", methods=["GET"])
def list_cameras():
    cameras = _memory.get_cameras(active_only=False)
    # Enrich with live stats
    live_stats = {s["camera_id"]: s for s in _camera_manager.get_all_stats()}
    for cam in cameras:
        stats = live_stats.get(cam["id"], {})
        cam["people_count"] = stats.get("people_count", 0)
        cam["fps"] = stats.get("fps", 0)
        cam["is_running"] = stats.get("is_running", False)
        cam["is_connected"] = stats.get("is_connected", False)
        cam["last_error"] = stats.get("last_error")
    return jsonify(cameras)


@cameras_bp.route("/api/cameras", methods=["POST"])
def add_camera():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    name = data.get("name", "").strip()
    url = data.get("url", "").strip()
    area = data.get("area", "default").strip()
    plant = data.get("plant", "Plant 1").strip()

    if not name or not url:
        return jsonify({"error": "name and url are required"}), 400

    camera_id = _memory.add_camera(name, url, area, plant)

    # Start processing immediately
    _camera_manager.start_camera(camera_id, name, url, area, plant)

    return jsonify({"id": camera_id, "name": name, "url": url, "area": area, "plant": plant}), 201


@cameras_bp.route("/api/cameras/<int:camera_id>", methods=["PUT"])
def update_camera(camera_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    cam = _memory.get_camera(camera_id)
    if not cam:
        return jsonify({"error": "Camera not found"}), 404

    name = data.get("name")
    url = data.get("url")
    area = data.get("area")
    plant = data.get("plant")
    is_active = data.get("is_active")

    ok = _memory.update_camera(camera_id, name, url, area, plant, is_active)
    if ok:
        # If camera is running, we might need to restart it with new config
        # For now, let's just update the processor if it exists
        proc = _camera_manager.get_processor(camera_id)
        if proc:
            if name: proc.name = name
            if url:
                # URL change requires a restart
                _camera_manager.start_camera(camera_id, name or proc.name, url, area or proc.area, plant or proc.plant)
            else:
                if area: proc.area = area
                if plant: proc.plant = plant

    return jsonify(_memory.get_camera(camera_id))


@cameras_bp.route("/api/cameras/<int:camera_id>", methods=["DELETE"])
def delete_camera(camera_id):
    cam = _memory.get_camera(camera_id)
    if not cam:
        return jsonify({"error": "Camera not found"}), 404

    _camera_manager.stop_camera(camera_id)
    _memory.delete_camera(camera_id)
    return jsonify({"deleted": camera_id})


# =========================================================================
# CAMERA VIDEO FEED
# =========================================================================

@cameras_bp.route("/api/cameras/<int:camera_id>/feed")
def camera_feed(camera_id):
    """MJPEG stream for a specific camera."""
    def generate():
        while True:
            frame_bytes = _camera_manager.get_camera_frame(camera_id)
            if frame_bytes:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                       frame_bytes + b'\r\n')
            else:
                time.sleep(0.1)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


# =========================================================================
# ZONES & SNAPSHOT
# =========================================================================

@cameras_bp.route("/api/cameras/<int:camera_id>/snapshot")
def camera_snapshot(camera_id):
    """Return a single JPEG frame for the camera."""
    frame_bytes = _camera_manager.get_camera_frame(camera_id)
    if frame_bytes:
        return Response(frame_bytes, mimetype='image/jpeg')
    return jsonify({"error": "Frame not available"}), 404


@cameras_bp.route("/api/cameras/<int:camera_id>/frame")
def camera_frame(camera_id):
    """Return the latest pre-encoded JPEG frame (optimized for high-FPS polling)."""
    frame_bytes = _camera_manager.get_camera_frame(camera_id)
    if frame_bytes:
        resp = Response(frame_bytes, mimetype='image/jpeg')
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
    # Return a 1x1 transparent pixel if no frame yet (avoids broken image errors)
    return Response(b'', status=204)


@cameras_bp.route("/api/cameras/<int:camera_id>/zones", methods=["GET"])
def get_camera_zones(camera_id):
    """Get zone configurations for a camera."""
    cam = _memory.get_camera(camera_id)
    if not cam:
        return jsonify({"error": "Camera not found"}), 404
        
    import json
    zone_a = json.loads(cam.get("zone_a") or "[]")
    zone_b = json.loads(cam.get("zone_b") or "[]")
    
    # Generate default zones relative to the frame if missing? The frontend handles empty array differently now, let's just return what we have or config globally.
    if not zone_a or not zone_b:
        import config
        defaults = config.get_zones_raw()
        zone_a = zone_a or defaults.get("zone_a", [])
        zone_b = zone_b or defaults.get("zone_b", [])

    return jsonify({"zone_a": zone_a, "zone_b": zone_b})


@cameras_bp.route("/api/cameras/<int:camera_id>/zones", methods=["POST"])
def save_camera_zones(camera_id):
    """Save zone configurations for a camera."""
    data = request.get_json()
    if not data or "zone_a" not in data or "zone_b" not in data:
        return jsonify({"error": "Invalid zone data"}), 400

    cam = _memory.get_camera(camera_id)
    if not cam:
        return jsonify({"error": "Camera not found"}), 404

    success = _memory.update_camera_zones(camera_id, data["zone_a"], data["zone_b"])
    
    # Notify camera processor to reload
    proc = _camera_manager.get_processor(camera_id)
    if proc:
        proc.reload_zones()

    if success:
        return jsonify({"success": True})
    return jsonify({"error": "Failed to save zones"}), 500


# =========================================================================
# AREA MONITORING
# =========================================================================

@cameras_bp.route("/api/areas")
def area_stats():
    """Return aggregated people counts per area."""
    return jsonify(_camera_manager.get_area_stats())


@cameras_bp.route("/api/plants")
def plant_stats():
    """Return aggregated people counts per plant."""
    return jsonify(_camera_manager.get_plant_stats())


@cameras_bp.route("/api/area_alerts")
def area_alerts():
    """Return activity reduction alerts."""
    limit = request.args.get("limit", 50, type=int)
    return jsonify(_area_monitor.get_alerts(limit=limit))


@cameras_bp.route("/api/area_status")
def area_status():
    """Return current monitoring status for each area."""
    return jsonify(_area_monitor.get_status())


@cameras_bp.route("/api/areas/limits", methods=["GET"])
def get_area_limits():
    """Return configured people limits for all areas."""
    return jsonify(_memory.get_area_limits())


@cameras_bp.route("/api/areas/<area>/limit", methods=["PUT"])
def set_area_limit(area):
    """Set the people limit for an area."""
    data = request.get_json()
    if not data or "limit" not in data:
        return jsonify({"error": "Missing 'limit' in request body"}), 400
        
    try:
        limit = int(data["limit"])
    except ValueError:
        return jsonify({"error": "Limit must be an integer"}), 400

    success = _memory.update_area_limit(area, limit)
    if success:
        _area_monitor.set_area_limit(area, limit)
        return jsonify({"success": True, "area": area, "limit": limit})
    return jsonify({"error": "Failed to update area limit"}), 500


# =========================================================================
# BUILDING TOTAL
# =========================================================================

@cameras_bp.route("/api/building_total", methods=["GET"])
def building_total():
    """Return the total people count aggregated across all active cameras."""
    stats = _camera_manager.get_all_stats()
    total = sum(s.get("people_count", 0) for s in stats)
    return jsonify({"total": total})
