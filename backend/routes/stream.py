import time
import json
from flask import Blueprint, Response, stream_with_context

stream_bp = Blueprint('stream', __name__)

_camera_manager = None

def init_stream_routes(camera_manager):
    global _camera_manager
    _camera_manager = camera_manager

@stream_bp.route('/api/stream/spatial')
def stream_spatial():
    """Server-Sent Events endpoint for real-time spatial data."""
    def generate():
        while True:
            if _camera_manager:
                data = _camera_manager.get_spatial_data()
                # Yield the data as an SSE event
                yield f"data: {json.dumps(data)}\n\n"
            
            # Control the frame rate of the SSE stream (e.g., 5-10 Hz is plenty for UI)
            time.sleep(0.1)

    return Response(stream_with_context(generate()), mimetype='text/event-stream')
