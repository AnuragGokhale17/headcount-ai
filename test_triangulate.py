import json
import numpy as np
import cv2
import yaml

with open("/home/auto-calibration-ms/server/projects/project_20260528_032417_6056/output/alignment_data/alignment_data.json", "r") as f:
    data = json.load(f)

pts0 = np.array([item[0] for item in data], dtype=np.float32).T
pts1 = np.array([item[1] for item in data], dtype=np.float32).T
layout_pts = np.array([item[2] for item in data], dtype=np.float32)

with open("/home/auto-calibration-ms/server/projects/project_20260528_032417_6056/output/multi_view_results/BA_output/results_ba/refined/camInfo_00.yaml", "r") as f:
    cam0 = yaml.safe_load(f)
with open("/home/auto-calibration-ms/server/projects/project_20260528_032417_6056/output/multi_view_results/BA_output/results_ba/refined/camInfo_01.yaml", "r") as f:
    cam1 = yaml.safe_load(f)

P0 = np.array(cam0['projectionMatrix_3x4'])
P1 = np.array(cam1['projectionMatrix_3x4'])

points4D = cv2.triangulatePoints(P0, P1, pts0, pts1)
points3D = points4D[:3, :] / points4D[3, :]
points3D = points3D.T

print("Triangulated 3D points:")
print(points3D)

print("Layout points:")
print(layout_pts)

pts_ground = points3D[:, :2]

print("Ground plane 2D points (X, Y):")
print(pts_ground)

H, mask = cv2.findHomography(pts_ground, layout_pts)
print("Homography:")
print(H)

if H is None:
    print("Homography is None!")
