import sys

def analyze_traj(file_path):
    tracklets = {}
    try:
        with open(file_path, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) < 2:
                    continue
                try:
                    tid = int(parts[1])
                    tracklets[tid] = tracklets.get(tid, 0) + 1
                except ValueError:
                    continue
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return

    lengths = list(tracklets.values())
    if not lengths:
        print(f"No tracklets found in {file_path}")
        return

    print(f"Analysis for {file_path}:")
    print(f"  Total tracklets: {len(tracklets)}")
    print(f"  Min length: {min(lengths)}")
    print(f"  Max length: {max(lengths)}")
    print(f"  Avg length: {sum(lengths)/len(lengths):.2f}")
    print(f"  Tracklets with length >= 90: {len([l for l in lengths if l >= 90])}")

if __name__ == "__main__":
    analyze_traj("auto-magic-calib/projects/project_20260526_233331_6539/output/single_view_results/cam_00/trajDump_Stream_0_3d.txt")
    analyze_traj("auto-magic-calib/projects/project_20260526_233331_6539/output/single_view_results/cam_01/trajDump_Stream_0_3d.txt")
    analyze_traj("auto-magic-calib/projects/project_20260526_233331_6539/output/single_view_results/cam_02/trajDump_Stream_0_3d.txt")
