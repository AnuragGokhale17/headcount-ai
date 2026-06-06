import sys
import traceback
import yaml
import cv2

try:
    with open("/home/auto-calibration-ms/configs/config_AutoMagicCalib/mv_amc_config.yaml", "r") as f:
        cfg = yaml.safe_load(f)

    import core.camera_estimation.layout_alignment_post_process as lapp

    original_undistortPoints = cv2.undistortPoints

    def hooked_undistortPoints(*args, **kwargs):
        print(">>> cv2.undistortPoints called!")
        print("  arg0 type:", type(args[0]))
        print("  arg1 (K) type:", type(args[1]))
        if len(args) > 2:
            print("  arg2 (D) type:", type(args[2]), "val:", args[2])
        res = original_undistortPoints(*args, **kwargs)
        return res

    cv2.undistortPoints = hooked_undistortPoints

    lapp.generate_transform_from_alignment_data(
        "/home/auto-calibration-ms/server/projects/project_20260528_032417_6056/output/alignment_data/alignment_data.json",
        "/home/auto-calibration-ms/server/projects/project_20260528_032417_6056/output/multi_view_results",
        cfg
    )
except Exception as e:
    print("Caught:", type(e), e)
    traceback.print_exc()
