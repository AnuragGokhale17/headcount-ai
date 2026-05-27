import sys

def analyze_time(file_path):
    frames = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) < 1:
                    continue
                try:
                    fid = int(parts[0])
                    frames.append(fid)
                except ValueError:
                    continue
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return

    if not frames:
        print(f"No frames found in {file_path}")
        return

    print(f"Time range for {file_path}:")
    print(f"  Min frame: {min(frames)}")
    print(f"  Max frame: {max(frames)}")
    print(f"  Total frames: {max(frames) - min(frames) + 1}")

if __name__ == "__main__":
    analyze_time("auto-magic-calib/projects/project_20260526_233331_6539/output/single_view_results/cam_00/trajDump_Stream_0_3d.txt")
    analyze_time("auto-magic-calib/projects/project_20260526_233331_6539/output/single_view_results/cam_01/trajDump_Stream_0_3d.txt")
    analyze_time("auto-magic-calib/projects/project_20260526_233331_6539/output/single_view_results/cam_02/trajDump_Stream_0_3d.txt")
