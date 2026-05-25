from geocalib import GeoCalib
import torch

# Choose device
device = "cuda" if torch.cuda.is_available() else "cpu"

# Load model
model = GeoCalib().to(device)

# Load image
image = model.load_image("D:\\Work\\Projects\\headcount\\recordings\\test.png").to(device)

# Run calibration
result = model.calibrate(image)

print("Camera:", result["camera"])
print("Gravity:", result["gravity"])