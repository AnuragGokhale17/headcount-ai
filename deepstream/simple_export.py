import torch
import torch.nn as nn
from ultralytics import YOLO
import onnx

class DeepStreamRaw(nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, x):
        # 1. Get raw output from Detect head [B, 84, 8400]
        y = self.model(x)
        if isinstance(y, (list, tuple)):
            y = y[0]
            
        # 2. Transpose to [B, 8400, 84]
        y = y.transpose(1, 2)
        
        # 3. Convert XYWH to Corners
        cx, cy, w, h = y[:, :, 0:1], y[:, :, 1:2], y[:, :, 2:3], y[:, :, 3:4]
        x1 = cx - w / 2
        y1 = cy - h / 2
        x2 = cx + w / 2
        y2 = cy + h / 2
        
        # 4. Extract Person Class (Index 4 is first class, usually Person)
        # Note: We take ALL classes but we'll filter in DeepStream
        scores, labels = torch.max(y[:, :, 4:], dim=-1, keepdim=True)
        
        # 5. Return [x1, y1, x2, y2, score, label]
        return torch.cat([x1, y1, x2, y2, scores, labels.float()], dim=-1)

def export():
    print("🚀 Forcing Raw Export via JIT Trace...")
    yolo = YOLO("deepstream/yolo26l.pt")
    model_inner = yolo.model.fuse().eval()
    
    # Wrap for DeepStream
    full_model = DeepStreamRaw(model_inner)
    dummy_input = torch.randn(1, 3, 640, 640) # Use batch 1 for tracing
    
    print("🧠 Tracing model (capturing graph)...")
    # This bypasses the FX graph and Scripting errors
    traced_model = torch.jit.trace(full_model, dummy_input)
    
    print("📦 Exporting to ONNX...")
    torch.onnx.export(
        traced_model,
        dummy_input,
        "deepstream/yolo26l.onnx",
        opset_version=12,
        input_names=['images'],
        output_names=['output0'],
        dynamic_axes={'images': {0: 'batch'}, 'output0': {0: 'batch'}}
    )
    print("✅ Success! Raw model saved to deepstream/yolo26l.onnx")

if __name__ == "__main__":
    export()
