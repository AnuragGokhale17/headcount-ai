"""Video streaming route."""
from flask import Blueprint, Response
import time

video_bp = Blueprint('video', __name__)

_camera_manager = None

def init_video_routes(camera_manager):
    global _camera_manager
    _camera_manager = camera_manager

@video_bp.route("/video_feed")
def video_feed():
    """Fallback feed: streams the first active camera."""
    def generate():
        while True:
            # Find the first active camera
            active_procs = list(_camera_manager._processors.values())
            if not active_procs:
                time.sleep(1)
                continue
                
            first_cam_id = active_procs[0].camera_id
            frame_bytes = _camera_manager.get_camera_frame(first_cam_id)
            if frame_bytes:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                       frame_bytes + b'\r\n')
            else:
                time.sleep(0.1)

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")
