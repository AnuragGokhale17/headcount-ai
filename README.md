# Headcount AI - Multi-Container Pipeline

A real-time headcount monitoring system using NVIDIA DeepStream 9.0, Flask, and React.

## 🏗️ Architecture
- **DeepStream (AI Engine):** Handles RTSP ingestion, YOLOv26 inference, and object tracking.
- **Backend (Flask):** Serves the dashboard API and syncs configurations with the AI engine.
- **MediaMTX (Streaming):** Provides low-latency WebRTC/RTSP stream bridging.
- **Redis (Data Bus):** Real-time messaging between DeepStream and the Backend.

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- NVIDIA Container Toolkit (for GPU support)
- WSL2 (if on Windows)

### Running the System
```powershell
# 1. Start all services
docker-compose up -d

# 2. Watch the AI initialization (First run takes ~5 mins)
docker logs headcount_deepstream -f
```

Access the dashboard at: **http://localhost:5000**

## 🔧 Environment Setup
The system automatically handles:
- **NumPy/OpenCV Fixing:** Downgrades incompatible NumPy 2.x versions to ensure stability.
- **YOLO Parser Build:** Compiles the custom bounding box parser on first launch.
- **Stream Sync:** Automatically bridges DeepStream metadata to the Redis-backed UI.

## 🛠️ Configuration
- Edit `deepstream/config_infer_yolo.txt` for AI sensitivity.
- Edit `backend/camera_manager.py` for camera sources.
