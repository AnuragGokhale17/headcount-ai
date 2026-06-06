import sqlite3
import os
import json
import numpy as np

def load_amc_yaml(filepath):
    """Parse an AMC YAML file and compute the pixel-to-world homography matrix."""
    import yaml
    with open(filepath, 'r') as f:
        content = yaml.safe_load(f)
    
    proj_flat = content["projectionMatrix_3x4_w2p"]
    P = np.array(proj_flat, dtype=np.float64).reshape(3, 4)
    
    # Extract 3x3 matrix by dropping the Z column (index 2)
    M_w2p = P[:, [0, 1, 3]]
    
    # Invert to get Pixel-to-World mapping
    H_p2w = np.linalg.inv(M_w2p)
    
    # Normalize so bottom-right element is 1.0
    if H_p2w[2, 2] != 0:
        H_p2w = H_p2w / H_p2w[2, 2]
    
    return H_p2w.tolist()

def main():
    db_path = os.path.join("data", "memory.db")
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}!")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Map recording files to cameras
    recordings_dir = "recordings3"
    video_files = [
        "cam2_20260603_160600.mp4",
        "cam3_20260603_160600.mp4",
        "cam8_20260603_160600.mp4",
        "cam10_20260603_160600.mp4"
    ]

    # Path inside the DeepStream container
    video_urls = [f"file:///workspace/recordings3/{f}" for f in video_files]

    # Real AMC calibration directory
    calibration_dir = "amc_calibration"

    # Try to find YAML files in the calibration directory
    all_amc_files = []
    if os.path.exists(calibration_dir):
        all_amc_files = [f for f in os.listdir(calibration_dir) if f.endswith('.yaml') and f != 'mv_amc_config.yaml']

    # Map cameras to potential AMC files (simple positional mapping for now)
    amc_files = []
    for i in range(len(video_files)):
        # Look for a file that contains 'cam1', 'cam2', etc.
        match = next((f for f in all_amc_files if f"cam{i+1}" in f.lower()), None)
        if match:
            amc_files.append(os.path.join(calibration_dir, match))
        else:
            # Fallback to positional if no name match
            if i < len(all_amc_files):
                amc_files.append(os.path.join(calibration_dir, all_amc_files[i]))
            else:
                amc_files.append(None)

    # Clear any existing cameras to ensure a clean slate
    print("🧹 Clearing old camera database records...")
    cursor.execute("DELETE FROM cameras")

    print(f"📝 Inserting {len(video_urls)} recorded cameras...")
    mock_cams = [
        ("Camera 1 - Entry", video_urls[0], "Entry Area", "Plant 1"),
        ("Camera 2 - Workspace",  video_urls[1], "Workspace Area", "Plant 1")
    ]
    cursor.executemany(
        "INSERT INTO cameras (name, url, area, plant, created_at, is_active) VALUES (?, ?, ?, ?, datetime('now'), 1)",
        mock_cams
    )
    conn.commit()

    # Now load AMC calibration matrices and attach them to each camera
    print("\n🔧 Loading NVIDIA AMC calibration matrices...")
    cursor.execute("SELECT id, name FROM cameras ORDER BY id")
    cameras = cursor.fetchall()

    for i, (cam_id, cam_name) in enumerate(cameras):
        if i < len(amc_files) and os.path.exists(amc_files[i]):
            try:
                matrix = load_amc_yaml(amc_files[i])
                cursor.execute(
                    "UPDATE cameras SET homography_matrix = ? WHERE id = ?",
                    (json.dumps(matrix), cam_id)
                )
                print(f"  ✅ Camera {cam_id} ({cam_name}): AMC matrix loaded from {amc_files[i]}")
            except Exception as e:
                print(f"  ⚠️ Camera {cam_id} ({cam_name}): Failed to load AMC — {e}")
        else:
            print(f"  ⚠️ Camera {cam_id} ({cam_name}): No AMC file found at {amc_files[i]}")
    
    conn.commit()
    
    # Print the final database state
    cursor.execute("SELECT id, name, url, area, is_active, homography_matrix FROM cameras")
    updated_cams = cursor.fetchall()
    print("\n✅ Database Updated Successfully!")
    print("=" * 80)
    for cam in updated_cams:
        has_calib = "✅ AMC Loaded" if cam[5] else "❌ No Calibration"
        print(f"ID: {cam[0]} | {cam[1]} | Area: {cam[3]} | Active: {cam[4]} | {has_calib}")
        print(f"  URL: {cam[2]}")
    print("=" * 80)
    print(f"\n🎯 SpatialMerger will deduplicate people across all {len(cameras)} cameras at runtime.")
        
    conn.close()

if __name__ == "__main__":
    main()
