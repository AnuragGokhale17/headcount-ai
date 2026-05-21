# Headcount AI - Project Documentation

A high-performance, multi-container AI pipeline for real-time headcount monitoring. This system leverages NVIDIA DeepStream for AI inference and tracking, with a Flask/React stack for management and visualization.

## 🏗️ Architecture Overview

The system is composed of several orchestrated services:

-   **AI Engine (DeepStream):** Located in `./deepstream/`.
    -   Handles RTSP ingestion and processing.
    -   Runs **YOLOv26** inference and object tracking (**BoT-SORT** / **NvDCF**).
    -   Communicates metadata to the backend via **Redis**.
    -   Managed by `ds_app.py` and initialized via `start_ds.sh`.
-   **Backend (Flask):** Located in `./backend/`.
    -   Provides REST API endpoints for the dashboard.
    -   Manages camera configurations, area monitoring, and occupancy alerts.
    -   Serves the production React frontend build.
    -   Entry point: `app.py`.
-   **Frontend (React):** Located in `./frontend/`.
    -   Modern dashboard built with React and Vite.
    -   Displays real-time stats, video streams, and historical data.
-   **Data Bus (Redis):**
    -   Acts as a real-time messaging layer between DeepStream and the Backend.
-   **Stream Bridge (MediaMTX):**
    -   Bridges internal RTSP streams to WebRTC for low-latency browser viewing.

## 🚀 Getting Started

### Prerequisites

-   **Docker & Docker Compose**
-   **NVIDIA Container Toolkit** (Required for GPU acceleration)
-   **NVIDIA GPU** (Compatible with DeepStream 9.0 and CUDA 12.6)

### Running the System

The entire pipeline is orchestrated via Docker Compose:

```bash
# Start all services
docker-compose up -d

# Monitor AI Engine initialization (First run builds custom parsers and engines)
docker logs headcount_deepstream -f
```

The dashboard will be accessible at: **http://localhost:5000**

## 🛠️ Development Guide

### Project Structure

-   `app.py`: Main entry point for the Flask backend and static file server.
-   `config.py`: Global configuration (thresholds, SMTP, colors, zones).
-   `backend/`:
    -   `routes/`: Modular API endpoints (video, stats, zones, audio, cameras).
    -   `camera_manager.py`: Logic for handling multiple camera sources.
    -   `ai_engine.py`: Higher-level analytics logic.
-   `deepstream/`:
    -   `ds_app.py`: The core DeepStream Python application.
    -   `start_ds.sh`: Boot script that handles `pyds` installation and YOLO parser compilation.
    -   `config_infer_yolo.txt`: DeepStream inference configuration.
    -   `models/`: AI model files (ONNX, TensorRT engines).
-   `frontend/`:
    -   `src/`: React components and API integration logic.
    -   `vite.config.js`: Build configuration.

### Build Processes

-   **Backend & Frontend:** The `backend/Dockerfile` uses a multi-stage build. It first builds the React app (`npm run build`) and then copies the output into the Flask environment.
-   **DeepStream Custom Parser:** The bounding box parser for YOLO is compiled on the first container launch within `deepstream/nvdsinfer_custom_impl_Yolo`.
-   **ReID Engine:** A TensorRT engine for ReID (OSNet) is built from ONNX on the first launch if not already present.

### Key Commands

-   **Rebuild Backend/Frontend:** `docker-compose build backend`
-   **Check DeepStream Logs:** `docker logs headcount_deepstream -f`
-   **Export ReID Model:** `python deepstream/export_osnet_reid.py` (Must be run if models are missing).

## 📝 Conventions

-   **Network Resilience:** Scripts like `start_ds.sh` include MTU optimizations and SSL bypasses to ensure stability in restricted network environments (e.g., WSL2 or Corporate VPNs).
-   **State Management:**
    -   **Real-time:** Redis is used for high-frequency AI metadata.
    -   **Persistent:** SQLite (via `backend/memory.py`) stores camera and zone configurations.
-   **CORS:** Backend handles CORS manually in `app.py` to facilitate local React development (`port 5173`).
