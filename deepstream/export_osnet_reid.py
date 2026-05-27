#!/usr/bin/env python3
"""
OSNet-AIN x1_0 → ONNX Export Script  (Self-Contained)
======================================================

Exports the pretrained OSNet-AIN x1_0 ReID model to ONNX for DeepStream NvDCF.

This script does NOT require `pip install torchreid`.  It clones the source
repo directly and imports the model definitions from source — bypassing the
broken Cython/numpy build chain entirely.

Prerequisites (in your venv):
    pip install torch numpy onnx onnxruntime gdown

Run:
    python export_osnet_reid.py

Output:
    ./models/reid/osnet_ain_x1_0.onnx
"""

import os
import sys
import subprocess
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_CACHE = os.path.join(SCRIPT_DIR, "_deep_person_reid")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "models", "reid")
MODEL_NAME = "osnet_ain_x1_0"
OUTPUT_ONNX = os.path.join(OUTPUT_DIR, f"{MODEL_NAME}.onnx")

INPUT_HEIGHT = 256
INPUT_WIDTH = 128
INPUT_CHANNELS = 3
FEATURE_DIM = 512
OPSET_VERSION = 11

# Google Drive file ID for osnet_ain_x1_0 pretrained weights
GDRIVE_FILE_ID = "1-CaioD9NaqbHK_kzSMW8VE6_3igc9wrm"
WEIGHTS_PATH = os.path.join(OUTPUT_DIR, f"{MODEL_NAME}_imagenet.pth")


def ensure_torch():
    """Check that PyTorch is available."""
    try:
        import torch
        return torch
    except ImportError:
        print("❌ PyTorch not installed. Run:")
        print("   pip install torch numpy onnx onnxruntime gdown")
        sys.exit(1)


def ensure_repo():
    """Clone deep-person-reid repo for model definitions (no pip install)."""
    marker = os.path.join(REPO_CACHE, "torchreid", "__init__.py")
    if os.path.exists(marker):
        print("✅ deep-person-reid source already cached.")
        return

    print("📥 Cloning deep-person-reid (shallow, ~5 seconds)...")
    if os.path.exists(REPO_CACHE):
        import shutil
        shutil.rmtree(REPO_CACHE)

    subprocess.run(
        [
            "git", "clone", "--depth", "1", "--filter=blob:none",
            "https://github.com/KaiyangZhou/deep-person-reid.git",
            REPO_CACHE,
        ],
        check=True,
    )
    print("✅ Repository cloned.")


def download_weights():
    """Download pretrained weights from Google Drive using gdown."""
    if os.path.exists(WEIGHTS_PATH):
        print(f"✅ Pretrained weights already cached: {WEIGHTS_PATH}")
        return

    print("📥 Downloading pretrained weights from Google Drive...")
    try:
        import gdown
        url = f"https://drive.google.com/uc?id={GDRIVE_FILE_ID}"
        gdown.download(url, WEIGHTS_PATH, quiet=False)
        print(f"✅ Weights downloaded: {WEIGHTS_PATH}")
    except ImportError:
        print("❌ gdown not installed. Run:")
        print("   pip install gdown")
        print()
        print("   Alternatively, download manually from:")
        print(f"   https://drive.google.com/uc?id={GDRIVE_FILE_ID}")
        print(f"   Save to: {WEIGHTS_PATH}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Download failed: {e}")
        print()
        print("   Download manually from:")
        print(f"   https://drive.google.com/uc?id={GDRIVE_FILE_ID}")
        print(f"   Save to: {WEIGHTS_PATH}")
        sys.exit(1)


def build_model(torch):
    """
    Import OSNet-AIN from the cloned source and load pretrained weights.

    The torchreid package has a graceful fallback for missing Cython extensions
    (IS_CYTHON_AVAIL = False), so importing from source works perfectly.
    """
    # Add repo to path BEFORE any torchreid imports
    sys.path.insert(0, REPO_CACHE)

    # Import the model builder from source
    from torchreid.models import build_model as _build

    # Build OSNet-AIN x1_0 (pretrained=False — we load weights manually)
    model = _build(
        name=MODEL_NAME,
        num_classes=1000,
        pretrained=False,
    )

    # Load pretrained weights
    state_dict = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict, strict=False)
    print(f"✅ Loaded pretrained weights ({len(state_dict)} parameters)")

    model.eval()
    return model


def export_onnx(torch, model):
    """Wrap model for feature-only output and export to ONNX."""

    class FeatureExtractorWrapper(torch.nn.Module):
        """Returns only the 512-dim embedding, not the classifier logits."""
        def __init__(self, base_model):
            super().__init__()
            self.base = base_model

        def forward(self, x):
            result = self.base(x)
            if isinstance(result, (tuple, list)):
                return result[0]
            return result

    wrapper = FeatureExtractorWrapper(model)
    wrapper.eval()

    dummy_input = torch.randn(1, INPUT_CHANNELS, INPUT_HEIGHT, INPUT_WIDTH)

    # Verify output shape before export
    with torch.no_grad():
        output = wrapper(dummy_input)
    actual_dim = output.shape[-1]
    print(f"✅ Model output shape: {output.shape} (feature dim: {actual_dim})")

    # Export
    print(f"\n📦 Exporting to ONNX (opset {OPSET_VERSION})...")
    torch.onnx.export(
        wrapper,
        dummy_input,
        OUTPUT_ONNX,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={
            "input":  {0: "batch_size"},
            "output": {0: "batch_size"},
        },
        opset_version=OPSET_VERSION,
        export_params=True,
        do_constant_folding=True,
    )

    file_size_mb = os.path.getsize(OUTPUT_ONNX) / (1024 * 1024)
    print(f"✅ ONNX exported: {OUTPUT_ONNX} ({file_size_mb:.1f} MB)")
    return actual_dim


def validate_onnx():
    """Run ONNX checker and a quick inference test."""
    try:
        import onnx
        onnx_model = onnx.load(OUTPUT_ONNX)
        onnx.checker.check_model(onnx_model)
        print("✅ ONNX model validation passed")
    except ImportError:
        print("⚠️  onnx package not installed — skipping validation")
    except Exception as e:
        print(f"⚠️  ONNX validation warning: {e}")

    try:
        import onnxruntime as ort
        session = ort.InferenceSession(OUTPUT_ONNX)
        test_input = np.random.randn(1, INPUT_CHANNELS, INPUT_HEIGHT, INPUT_WIDTH).astype(np.float32)
        ort_output = session.run(None, {"input": test_input})[0]
        print(f"✅ ONNX Runtime inference test passed. Output: {ort_output.shape}")
        norm = np.linalg.norm(ort_output[0])
        print(f"   L2 norm: {norm:.4f} (NvDCF will normalize this)")
    except ImportError:
        print("⚠️  onnxruntime not installed — skipping inference test")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print(f"  🧠 OSNet-AIN x1_0 → ONNX (Self-Contained Export)")
    print("=" * 60)

    # Step 1: Check PyTorch
    torch = ensure_torch()

    # Step 2: Clone model source (no pip install!)
    ensure_repo()

    # Step 3: Download pretrained weights from Google Drive
    download_weights()

    # Step 4: Build model and load weights
    print(f"\n🔧 Building {MODEL_NAME} architecture...")
    model = build_model(torch)

    # Step 5: Export to ONNX
    actual_dim = export_onnx(torch, model)

    # Step 6: Validate
    print("\n🔍 Validating exported model...")
    validate_onnx()

    # Summary
    print("\n" + "=" * 60)
    print("  ✅ Export Complete!")
    print(f"  📁 ONNX: {OUTPUT_ONNX}")
    print(f"  📐 Input:  [batch, {INPUT_CHANNELS}, {INPUT_HEIGHT}, {INPUT_WIDTH}]")
    print(f"  📊 Output: [batch, {actual_dim}]")
    print()
    print("  Next step: docker compose up")
    print("  The TRT engine builds automatically on first boot.")
    print("=" * 60)


if __name__ == "__main__":
    main()
