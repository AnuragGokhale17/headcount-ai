import onnxruntime as ort
import numpy as np
import cv2

def debug_inspect(path):
    print(f"🔍 Inspecting ONNX: {path}")
    session = ort.InferenceSession(path)
    input_name = session.get_inputs()[0].name
    
    img = np.ones((640, 640, 3), dtype=np.uint8) * 128
    x = img.transpose(2, 0, 1)
    x = np.expand_dims(x, axis=0).astype(np.float32) / 255.0
    x = np.repeat(x, 3, axis=0)
    
    outputs = session.run(None, {input_name: x})
    out = outputs[0] # Shape [3, 300, 6]
    
    print(f"📊 Top 5 Detections (Batch 0):")
    for i in range(5):
        det = out[0, i, :]
        print(f"  [{i}] Values: {det.tolist()}")

if __name__ == "__main__":
    debug_inspect("deepstream/yolo26l.onnx")
