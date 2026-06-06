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
        cam["total_detected"] = stats.get("total_detected", 0)
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

    # Start processing immediately and sync with DeepStream
    success, error = _camera_manager.start_camera(camera_id, name, url, area, plant)

    if not success:
        # Camera is in DB but engine failed to start. Tell user but keep in DB.
        return jsonify({
            "id": camera_id, 
            "name": name, 
            "warning": f"Camera added to database but engine failed to sync: {error}"
        }), 201

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


@cameras_bp.route("/api/cameras/<int:camera_id>/restart", methods=["POST"])
def restart_camera(camera_id):
    """Restart a camera engine."""
    success, error = _camera_manager.restart_camera(camera_id)
    if success:
        return jsonify({"success": True})
    return jsonify({"error": error or "Failed to restart camera"}), 500


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
    print(f"🎬 [DEBUG] Feed requested for camera {camera_id}")
    def generate():
        fail_count = 0
        while True:
            frame_bytes = _camera_manager.get_camera_frame(camera_id)
            if frame_bytes:
                fail_count = 0
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                       frame_bytes + b'\r\n')
            else:
                fail_count += 1
                if fail_count % 50 == 0:
                    print(f"⚠️ [DEBUG] Still no frame for camera {camera_id} (attempts: {fail_count})")
                time.sleep(0.1)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


@cameras_bp.route("/api/cameras/<int:camera_id>/heatmap")
def camera_heatmap(camera_id):
    """Return the spatial heatmap grid for a specific camera."""
    heatmap = _camera_manager.get_camera_heatmap(camera_id)
    if heatmap is not None:
        return jsonify(heatmap)
    return jsonify({"error": "Heatmap not available"}), 404


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


@cameras_bp.route("/api/cameras/<int:camera_id>/homography", methods=["GET"])
def get_camera_homography(camera_id):
    """Get homography matrix for a camera."""
    cam = _memory.get_camera(camera_id)
    if not cam:
        return jsonify({"error": "Camera not found"}), 404
        
    import json
    matrix = json.loads(cam.get("homography_matrix") or "null")
    return jsonify({"matrix": matrix})


@cameras_bp.route("/api/cameras/<int:camera_id>/homography", methods=["POST"])
def save_camera_homography(camera_id):
    """Save homography matrix for a camera."""
    data = request.get_json()
    if not data or "matrix" not in data:
        return jsonify({"error": "Invalid homography data"}), 400

    cam = _memory.get_camera(camera_id)
    if not cam:
        return jsonify({"error": "Camera not found"}), 404

    success = _memory.update_camera_homography(camera_id, data["matrix"])
    
    if success:
        # Update live merger
        _camera_manager.merger.update_camera_homography(camera_id, data["matrix"])
        return jsonify({"success": True})
    return jsonify({"error": "Failed to save homography"}), 500


@cameras_bp.route("/api/cameras/<int:camera_id>/calibrate", methods=["POST"])
def calibrate_camera(camera_id):
    """Compute and save homography matrix from 4 pairs of points."""
    import numpy as np
    import cv2
    
    data = request.get_json()
    if not data or "src_points" not in data or "dst_points" not in data:
        return jsonify({"error": "Invalid calibration data"}), 400

    src = np.array(data["src_points"], dtype=np.float32)
    dst = np.array(data["dst_points"], dtype=np.float32)

    if len(src) != 4 or len(dst) != 4:
        return jsonify({"error": "Need exactly 4 source and 4 destination points"}), 400

    # Compute homography matrix
    matrix, _ = cv2.findHomography(src, dst)
    
    if matrix is not None:
        # Convert to list for JSON storage
        matrix_list = matrix.tolist()
        success = _memory.update_camera_homography(camera_id, matrix_list)
        if success:
            # Update live merger
            _camera_manager.merger.update_camera_homography(camera_id, matrix_list)
            return jsonify({"success": True, "matrix": matrix_list})
            
    return jsonify({"error": "Calibration failed"}), 500


@cameras_bp.route("/api/cameras/<int:camera_id>/import_amc", methods=["POST"])
def import_amc_calibration(camera_id):
    """Import homography from NVIDIA AutoMagicCalib YAML file."""
    import yaml
    import numpy as np

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    try:
        content = yaml.safe_load(file.read())
    except Exception as e:
        return jsonify({"error": f"Failed to parse YAML: {str(e)}"}), 400

    if not isinstance(content, dict) or "projectionMatrix_3x4_w2p" not in content:
        return jsonify({"error": "YAML must contain 'projectionMatrix_3x4_w2p' key"}), 400

    proj_flat = content["projectionMatrix_3x4_w2p"]
    if not isinstance(proj_flat, list) or len(proj_flat) != 12:
        return jsonify({"error": "projectionMatrix_3x4_w2p must be a list of 12 numbers"}), 400

    try:
        # Convert flat list to 3x4 numpy array
        P = np.array(proj_flat, dtype=np.float32).reshape(3, 4)

        # Extract 3x3 matrix mapping (X_w, Y_w, 1) to (w*x_c, w*y_c, w) by dropping column index 2 (Z)
        M_w2p = P[:, [0, 1, 3]]

        # Compute the inverse to get Pixel-to-World mapping (H_p2w)
        H_p2w = np.linalg.inv(M_w2p)

        # Normalize the homography matrix so that the bottom-right element is 1.0
        if H_p2w[2, 2] != 0:
            H_p2w = H_p2w / H_p2w[2, 2]

        matrix_list = H_p2w.tolist()

        cam = _memory.get_camera(camera_id)
        if not cam:
            return jsonify({"error": "Camera not found"}), 404

        success = _memory.update_camera_homography(camera_id, matrix_list)
        if success:
            # Update live merger
            _camera_manager.merger.update_camera_homography(camera_id, matrix_list)
            return jsonify({
                "success": True, 
                "matrix": matrix_list,
                "msg": "Homography matrix successfully imported from AutoMagicCalib projection matrix."
            })
        else:
            return jsonify({"error": "Failed to update camera homography in DB"}), 500

    except np.linalg.LinAlgError:
        return jsonify({"error": "The computed World-to-Pixel matrix is singular and cannot be inverted."}), 400
    except Exception as e:
        return jsonify({"error": f"Internal error during matrix calculation: {str(e)}"}), 500


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
    """Return the total people count aggregated across all active cameras with spatial deduplication."""
    stats = _camera_manager.get_aggregated_stats()
    return jsonify({"total": stats.get("occupancy", 0)})

# =========================================================================
# AMC DYNAMIC CONFIGURATION
# =========================================================================

@cameras_bp.route("/api/amc/config", methods=["POST"])
def update_amc_config():
    """Update mv_amc_config.yaml with dynamic cam_dir list."""
    import yaml
    import os

    data = request.get_json()
    if not data or "video_count" not in data:
        return jsonify({"error": "Missing 'video_count' in request body"}), 400

    try:
        count = int(data["video_count"])
    except ValueError:
        return jsonify({"error": "video_count must be an integer"}), 400

    if count < 1:
        return jsonify({"error": "At least 1 video is required"}), 400

    cam_dirs = [f"cam_{i:02d}" for i in range(count)]

    # Path to mv_amc_config.yaml
    # __file__ is in backend/routes/cameras.py
    # We need to go up three levels to reach the project root (/app in Docker)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    yaml_path = os.path.join(base_dir, "auto-magic-calib", "compose", "ms", "mv_amc_config.yaml")

    try:
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)

        if config is None:
            config = {}

        config['cam_dir'] = cam_dirs

        with open(yaml_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        return jsonify({"success": True, "cam_dir": cam_dirs})
    except Exception as e:
        return jsonify({"error": f"Failed to update AMC config: {str(e)}"}), 500

