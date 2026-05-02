#!/bin/bash
set -e

echo "=============================================="
echo "  🧠 Headcount AI — DeepStream Bridge Boot"
echo "=============================================="

SETUP_FLAG="/workspace/deepstream/.setup_done"

if [ ! -f "$SETUP_FLAG" ]; then
    echo "🛠️ First-time setup detected. This may take a few minutes..."
    
    # 1. Temporarily disable the problematic NVIDIA repo to avoid 403 errors on non-essential packages
    echo "📦 Optimizing repositories..."
    mkdir -p /etc/apt/sources.list.d.bak
    mv /etc/apt/sources.list.d/cuda*.list /etc/apt/sources.list.d.bak/ 2>/dev/null || true

    echo "📦 Updating system repositories..."
    apt-get update -o "Acquire::https::Verify-Peer=false" || true

    # 2. Install Build Dependencies (with SSL bypass and skipping non-essentials)
    echo "📦 Installing build dependencies..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        -o "Acquire::https::Verify-Peer=false" \
        --no-install-recommends \
        --allow-unauthenticated \
        --fix-missing \
        build-essential \
        python3-gi python3-dev python3-gst-1.0 \
        python3-opencv libglib2.0-dev libgirepository1.0-dev \
        libcairo2-dev libssl-dev cmake g++ git \
        libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
        libhiredis-dev \
        libmpg123-dev libflac-dev libdvdread8 libdvdnav4 \
        libmjpegutils-2.1-0 libdca0 libmp3lame0 libjbig0 || true

    # 2b. Clean up old TensorRT engines to force rebuild on current hardware
    echo "🧹 Removing old TensorRT engines..."
    rm -f /workspace/deepstream/*.engine

    # Restore the NVIDIA repo for GPU acceleration later
    echo "📦 Restoring NVIDIA repositories..."
    mv /etc/apt/sources.list.d.bak/*.list /etc/apt/sources.list.d/ 2>/dev/null || true

    # 3. Clean up broken Numpy metadata
    echo "🧹 Cleaning up metadata..."
    rm -rf /usr/local/lib/python3.12/dist-packages/numpy-1.26.4.dist-info || true

    # 4. Install Python requirements
    echo "📦 Installing Python requirements..."
    export PIP_TRUSTED_HOST="pypi.org pypi.python.org files.pythonhosted.org"
    pip3 install --quiet \
        --trusted-host pypi.org \
        --trusted-host pypi.python.org \
        --trusted-host files.pythonhosted.org \
        --break-system-packages \
        --ignore-installed \
        -r /workspace/deepstream/requirements_ds.txt

    # 5. Build pyds from source (Required for Python 3.12)
    if python3 -c "import pyds" &> /dev/null; then
        echo "✅ pyds is already installed."
    else
        echo "🔨 Building pyds from source for Python 3.12..."
        git config --global http.sslVerify false
        
        cd /opt/nvidia/deepstream/deepstream/sources
        
        if [ ! -d "deepstream_python_apps" ]; then
            git clone --depth 1 https://github.com/NVIDIA-AI-IOT/deepstream_python_apps.git
        fi
        
        cd deepstream_python_apps
        git submodule update --init --recursive --depth 1
        
        cd bindings
        mkdir -p build && cd build
        cmake .. -DPYTHON_MAJOR_VERSION=3 -DPYTHON_MINOR_VERSION=12
        make -j$(nproc)
        
        # Install the .so file directly to dist-packages
        echo "📦 Installing pyds.so globally..."
        cp pyds*.so /usr/local/lib/python3.12/dist-packages/pyds.so
        
        echo "✅ pyds compiled and installed successfully."
    fi
    
    # FINAL VERIFICATION: Ensure everything is really working before creating the flag
    echo "🧪 Verifying core libraries (gi, pyds)..."
    if python3 -c "import gi; import pyds" &> /dev/null; then
        echo "✅ Verification passed."
        touch "$SETUP_FLAG"
    else
        echo "❌ Verification failed. Dependencies are NOT correctly installed."
        exit 1
    fi
else
    echo "🚀 Dependencies verified. Skipping installation."
fi

echo "🚀 Starting DeepStream Bridge..."
cd /workspace/deepstream
exec python3 ds_app.py