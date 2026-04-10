"""Zone configuration routes — GET/POST zones, GET snapshot."""
from flask import Blueprint, jsonify, request, Response
import config

zones_bp = Blueprint('zones', __name__)

_camera_manager = None

def init_zones_routes(camera_manager):
    global _camera_manager
    _camera_manager = camera_manager


@zones_bp.route("/api/zones", methods=["GET"])
def get_zones():
    """Return current zone polygon coordinates."""
    zones = config.get_zones_raw()
    return jsonify(zones)


@zones_bp.route("/api/zones", methods=["POST"])
def save_zones():
    """Save new zone polygon coordinates."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    zone_a = data.get("zone_a")
    zone_b = data.get("zone_b")

    if not zone_a or not zone_b:
        return jsonify({"error": "Both zone_a and zone_b are required"}), 400

    if len(zone_a) < 3 or len(zone_b) < 3:
        return jsonify({"error": "Each zone must have at least 3 points"}), 400

    version = config.save_zones(zone_a, zone_b)
    return jsonify({"success": True, "version": version, "message": "Zones saved and will reload on next frame"})


@zones_bp.route("/api/snapshot")
def snapshot():
    """Return a single JPEG frame from the first active camera for zone drawing."""
    if not _camera_manager:
        return jsonify({"error": "Camera manager not initialized"}), 503
        
    active_procs = list(_camera_manager._processors.values())
    if not active_procs:
        return jsonify({"error": "No active cameras"}), 503
        
    first_cam_id = active_procs[0].camera_id
    img_bytes = _camera_manager.get_camera_frame(first_cam_id)
    
    if img_bytes:
        return Response(img_bytes, mimetype='image/jpeg')
    return jsonify({"error": "No frame available"}), 503
