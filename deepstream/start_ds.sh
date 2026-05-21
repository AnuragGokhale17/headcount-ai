# #!/bin/bash
# set -e

# echo "=============================================="
# echo "  🧠 Headcount AI — DeepStream Triton Boot"
# echo "=============================================="

# # 1. PATH DEFINITIONS
# DS_DIR="/opt/nvidia/deepstream/deepstream"
# VENV_PATH="$DS_DIR/sources/deepstream_python_apps/pyds"

# # Temporary backup copy for debugging
# cp "$DS_DIR/user_deepstream_python_apps_install.sh" /workspace/deepstream/install_script_backup.sh || true


# # 2. SYSTEM PREP (SSL & Build Tools)
# echo "🔧 Ensuring system tools..."
# git config --global http.sslVerify false
# git config --global http.postBuffer 1048576000
# git config --global http.lowSpeedLimit 0
# git config --global http.lowSpeedTime 999999
# git config --global core.compression 0

# # Fix WSL2/VPN MTU issues causing Git/TLS failures
# echo "🌐 Optimizing network interface MTU..."
# for interface in $(ls /sys/class/net/); do
#     if [ "$interface" != "lo" ]; then
#         ip link set dev "$interface" mtu 1350 || true
#     fi
# done

# echo 'Acquire::https::Verify-Peer "false";' > /etc/apt/apt.conf.d/99verify-peer.conf
# dpkg --configure -a || true
# apt-get update || true
# apt-get install -y git cmake build-essential libglib2.0-dev \
#     libgstrtspserver-1.0-dev libgstreamer1.0-dev ca-certificates python3-pip python3-venv \
#     python3-dev python3-gi python3-gst-1.0 python-gi-dev libgirepository1.0-dev libcairo2-dev \
#     libglib2.0-dev-bin libtool m4 autoconf automake




# # 3. CHECK IF PYDS IS ACTUALLY WORKING
# # We try to activate and import. If it fails, we trigger a wipe and rebuild.
# PYDS_WORKS=0
# if [ -f "$VENV_PATH/bin/activate" ]; then
#     source "$VENV_PATH/bin/activate"
#     if python3 -c "import pyds" &>/dev/null; then
#         PYDS_WORKS=1
#     fi
# fi

# if [ "$PYDS_WORKS" -eq 0 ]; then
#     echo "⚠️ pyds is missing or broken. Wiping and starting a clean build..."
#     cd "$DS_DIR"
#     rm -rf sources/deepstream_python_apps
    
#     # Run official build script
#     # This script clones the repo and creates a venv at sources/deepstream_python_apps/pyds
#     echo "🩹 Patching NVIDIA build script to use shallow clones..."
#     sed -i 's|git clone -b|git clone --depth 1 -b|g' user_deepstream_python_apps_install.sh
#     sed -i 's|git submodule update --init|git submodule update --init --depth 1|g' user_deepstream_python_apps_install.sh

#     echo "📡 Running official NVIDIA build script (this takes 2-5 minutes)..."
#     bash user_deepstream_python_apps_install.sh -b

    
#     # Activate the newly created venv
#     source "$VENV_PATH/bin/activate"
# else
#     echo "✅ Existing pyds environment detected and working."
#     source "$VENV_PATH/bin/activate"
# fi

# # 4. INSTALL APP DEPENDENCIES (Into the active venv)
# echo "🔨 Installing application dependencies..."
# # We pin pydantic to 2.10.6 to satisfy both FastAPI and DeepStream Triton's internal libs
# pip3 install "numpy<2.0" "opencv-python-headless<4.10" "pydantic==2.10.6" \
#     fastapi uvicorn redis requests python-multipart --force-reinstall

# # 5. BUILD YOLO PARSER (The "No Boxes" Fix)
# CUSTOM_PARSER_DIR="/workspace/deepstream/nvdsinfer_custom_impl_Yolo"
# if [ ! -f "$CUSTOM_PARSER_DIR/libnvdsinfer_custom_impl_Yolo.so" ]; then
#     echo "🔨 Preparing YOLO Bounding Box Parser..."
#     rm -rf /tmp/ds_yolo
#     git clone https://github.com/marcoslucianops/DeepStream-Yolo /tmp/ds_yolo
#     mkdir -p "$CUSTOM_PARSER_DIR"
#     cp -r /tmp/ds_yolo/nvdsinfer_custom_impl_Yolo/* "$CUSTOM_PARSER_DIR/"
    
#     cd "$CUSTOM_PARSER_DIR"
#     export CUDA_VER=12.6
#     make clean || true
#     make -j$(nproc)
#     echo "✅ YOLO Parser compiled."
# fi

# # 6. BUILD REID ENGINE (OSNet-AIN x1_0 for NvDCF tracker)
# REID_ONNX="/workspace/deepstream/models/reid/osnet_ain_x1_0.onnx"
# REID_ENGINE="/workspace/deepstream/models/reid/osnet_ain_x1_0.engine"

# if [ -f "$REID_ONNX" ] && [ ! -f "$REID_ENGINE" ]; then
#     echo "🧠 Building ReID TensorRT engine from ONNX (FP16)..."
#     echo "   This takes 1-3 minutes on first boot only."
#     /usr/src/tensorrt/bin/trtexec \
#         --onnx="$REID_ONNX" \
#         --saveEngine="$REID_ENGINE" \
#         --fp16 \
#         --minShapes=input:1x3x256x128 \
#         --optShapes=input:16x3x256x128 \
#         --maxShapes=input:32x3x256x128 \
#         --workspace=1024
    
#     if [ -f "$REID_ENGINE" ]; then
#         echo "✅ ReID TensorRT engine built successfully."
#     else
#         echo "⚠️  ReID engine build failed. NvDCF will try inline build (slower)."
#     fi
# elif [ -f "$REID_ENGINE" ]; then
#     echo "✅ ReID TensorRT engine already exists — skipping build."
# elif [ ! -f "$REID_ONNX" ]; then
#     echo "⚠️  ReID ONNX model not found at $REID_ONNX"
#     echo "   Run 'python export_osnet_reid.py' on the host first!"
#     echo "   Tracker will run WITHOUT ReID (basic NvDCF only)."
# fi

# # 7. FINAL VERIFICATION
# echo "🔍 Verifying final environment..."
# python3 -c "import pyds; import cv2; import numpy; print(f'🚀 SUCCESS! Ready on NumPy {numpy.__version__}')"

# # 8. START APP
# echo "🚀 Starting DeepStream Bridge..."
# cd /workspace/deepstream
# export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$CUSTOM_PARSER_DIR
# chmod -R 777 /workspace/deepstream 2>/dev/null || true

# # Execution will now use the virtual environment's python
# exec python3 ds_app.py



#!/bin/bash
set -e

echo "=============================================="
echo "  🧠 Headcount AI — DeepStream Triton Boot"
echo "=============================================="

# 1. PATH DEFINITIONS
DS_DIR="/opt/nvidia/deepstream/deepstream"
VENV_PATH="$DS_DIR/sources/deepstream_python_apps/pyds"

# Temporary backup copy for debugging
cp "$DS_DIR/user_deepstream_python_apps_install.sh" /workspace/deepstream/install_script_backup.sh || true


# 2. SYSTEM PREP (SSL & Build Tools)
echo "🔧 Ensuring system tools..."

# --- CRITICAL FIXES FOR GNUTLS RECV ERROR (-110) ---
git config --global http.sslVerify false
git config --global http.version HTTP/1.1        # 🌟 FORCE HTTP/1.1 (Disables flaky HTTP/2 multiplexing)
git config --global http.postBuffer 1048576000     # 1GB buffer limit
git config --global https.postBuffer 1048576000    # Mirror for HTTPS
git config --global core.compression -1            # 🌟 Re-enable standard compression (prevents massive payload drops)
git config --global http.lowSpeedLimit 0
git config --global http.lowSpeedTime 999999

# Fix WSL2/VPN MTU issues causing Git/TLS failures
echo "🌐 Optimizing network interface MTU..."
for interface in $(ls /sys/class/net/); do
    if [ "$interface" != "lo" ]; then
        ip link set dev "$interface" mtu 1350 || true
    fi
done

echo 'Acquire::https::Verify-Peer "false";' > /etc/apt/apt.conf.d/99verify-peer.conf
dpkg --configure -a || true
apt-get update || true
apt-get install -y git cmake build-essential libglib2.0-dev \
    libgstrtspserver-1.0-dev libgstreamer1.0-dev ca-certificates python3-pip python3-venv \
    python3-dev python3-gi python3-gst-1.0 python-gi-dev libgirepository1.0-dev libcairo2-dev \
    libglib2.0-dev-bin libtool m4 autoconf automake


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
    
    # Run official build script
    # This script clones the repo and creates a venv at sources/deepstream_python_apps/pyds
    echo "🩹 Patching NVIDIA build script to use shallow clones..."
    sed -i 's|git clone -b|git clone --depth 1 -b|g' user_deepstream_python_apps_install.sh
    sed -i 's|git submodule update --init|git submodule update --init --depth 1|g' user_deepstream_python_apps_install.sh

    echo "📡 Running official NVIDIA build script (with retry resiliency)..."
    MAX_RETRIES=3
    RETRY_COUNT=0
    SUCCESS=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        # Always clean up before an attempt to prevent the "destination already exists" Git error
        rm -rf sources/deepstream_python_apps
        
        # We run the installer. If it succeeds, we exit the loop.
        if bash user_deepstream_python_apps_install.sh -b; then
            SUCCESS=1
            break
        else
            RETRY_COUNT=$((RETRY_COUNT+1))
            echo "⚠️ NVIDIA Build Script failed (Attempt $RETRY_COUNT of $MAX_RETRIES). Retrying in 5 seconds..."
            sleep 5
        fi
    done

    if [ $SUCCESS -eq 0 ]; then
        echo "❌ ERROR: Official NVIDIA build script failed after $MAX_RETRIES attempts."
        exit 1
    fi
    
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
    # 🌟 Added --depth 1 to safeguard against TLS drop issues here too
    git clone --depth 1 https://github.com/marcoslucianops/DeepStream-Yolo /tmp/ds_yolo
    mkdir -p "$CUSTOM_PARSER_DIR"
    cp -r /tmp/ds_yolo/nvdsinfer_custom_impl_Yolo/* "$CUSTOM_PARSER_DIR/"
    
    cd "$CUSTOM_PARSER_DIR"
    export CUDA_VER=12.6
    make clean || true
    make -j$(nproc)
    echo "✅ YOLO Parser compiled."
fi

# 6. BUILD REID ENGINE (OSNet-AIN x1_0 for NvDCF tracker)
REID_ONNX="/workspace/deepstream/models/reid/osnet_ain_x1_0.onnx"
REID_ENGINE="/workspace/deepstream/models/reid/osnet_ain_x1_0.engine"

if [ -f "$REID_ONNX" ] && [ ! -f "$REID_ENGINE" ]; then
    echo "🧠 Building ReID TensorRT engine from ONNX (FP16)..."
    echo "   This takes 1-3 minutes on first boot only."
    /usr/src/tensorrt/bin/trtexec \
        --onnx="$REID_ONNX" \
        --saveEngine="$REID_ENGINE" \
        --fp16 \
        --minShapes=input:1x3x256x128 \
        --optShapes=input:16x3x256x128 \
        --maxShapes=input:32x3x256x128 \
        --workspace=1024
    
    if [ -f "$REID_ENGINE" ]; then
        echo "✅ ReID TensorRT engine built successfully."
    else
        echo "⚠️  ReID engine build failed. NvDCF will try inline build (slower)."
    fi
elif [ -f "$REID_ENGINE" ]; then
    echo "✅ ReID TensorRT engine already exists — skipping build."
elif [ ! -f "$REID_ONNX" ]; then
    echo "⚠️  ReID ONNX model not found at $REID_ONNX"
    echo "   Run 'python export_osnet_reid.py' on the host first!"
    echo "   Tracker will run WITHOUT ReID (basic NvDCF only)."
fi

# 7. FINAL VERIFICATION
echo "🔍 Verifying final environment..."
python3 -c "import pyds; import cv2; import numpy; print(f'🚀 SUCCESS! Ready on NumPy {numpy.__version__}')"

# 8. START APP
echo "🚀 Starting DeepStream Bridge..."
cd /workspace/deepstream
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$CUSTOM_PARSER_DIR
chmod -R 777 /workspace/deepstream 2>/dev/null || true

# Execution will now use the virtual environment's python
exec python3 ds_app.py