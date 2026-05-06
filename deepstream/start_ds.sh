#!/bin/bash
set -e

echo "=============================================="
echo "  🧠 Headcount AI — DeepStream Triton Boot"
echo "=============================================="

# 1. PATH DEFINITIONS
DS_DIR="/opt/nvidia/deepstream/deepstream"
VENV_PATH="$DS_DIR/sources/deepstream_python_apps/pyds"

# 2. SYSTEM PREP (SSL & Build Tools)
echo "🔧 Ensuring system tools..."
git config --global http.sslVerify false
dpkg --configure -a || true
apt-get update || true
apt-get install -y git cmake build-essential libglib2.0-dev \
    libgstrtspserver-1.0-dev libgstreamer1.0-dev ca-certificates python3-pip python3-venv

# 3. CHECK IF PYDS IS ACTUALLY WORKING
# We try to activate and import. If it fails, we trigger a wipe and rebuild.
PYDS_WORKS=0
if [ -f "$VENV_PATH/bin/activate" ]; then
    source "$VENV_PATH/bin/activate"
    if python3 -c "import pyds" &>/dev/null; then
        PYDS_WORKS=1
    fi
fi

if [ "$PYDS_WORKS" -eq 0 ]; then
    echo "⚠️ pyds is missing or broken. Wiping and starting a clean build..."
    cd "$DS_DIR"
    rm -rf sources/deepstream_python_apps
    
    # Run official build script
    # This script clones the repo and creates a venv at sources/deepstream_python_apps/pyds
    echo "📡 Running official NVIDIA build script (this takes 2-5 minutes)..."
    bash user_deepstream_python_apps_install.sh -b
    
    # Activate the newly created venv
    source "$VENV_PATH/bin/activate"
else
    echo "✅ Existing pyds environment detected and working."
    source "$VENV_PATH/bin/activate"
fi

# 4. INSTALL APP DEPENDENCIES (Into the active venv)
echo "🔨 Installing application dependencies..."
# We pin pydantic to 2.10.6 to satisfy both FastAPI and DeepStream Triton's internal libs
pip3 install "numpy<2.0" "opencv-python-headless<4.10" "pydantic==2.10.6" \
    fastapi uvicorn redis requests python-multipart --force-reinstall

# 5. BUILD YOLO PARSER (The "No Boxes" Fix)
CUSTOM_PARSER_DIR="/workspace/deepstream/nvdsinfer_custom_impl_Yolo"
if [ ! -f "$CUSTOM_PARSER_DIR/libnvdsinfer_custom_impl_Yolo.so" ]; then
    echo "🔨 Preparing YOLO Bounding Box Parser..."
    rm -rf /tmp/ds_yolo
    git clone https://github.com/marcoslucianops/DeepStream-Yolo /tmp/ds_yolo
    mkdir -p "$CUSTOM_PARSER_DIR"
    cp -r /tmp/ds_yolo/nvdsinfer_custom_impl_Yolo/* "$CUSTOM_PARSER_DIR/"
    
    cd "$CUSTOM_PARSER_DIR"
    export CUDA_VER=12.6
    make clean || true
    make -j$(nproc)
    echo "✅ YOLO Parser compiled."
fi

# 6. FINAL VERIFICATION
echo "🔍 Verifying final environment..."
python3 -c "import pyds; import cv2; import numpy; print(f'🚀 SUCCESS! Ready on NumPy {numpy.__version__}')"

# 7. START APP
echo "🚀 Starting DeepStream Bridge..."
cd /workspace/deepstream
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$CUSTOM_PARSER_DIR
chmod -R 777 /workspace/deepstream 2>/dev/null || true

# Execution will now use the virtual environment's python
exec python3 ds_app.py