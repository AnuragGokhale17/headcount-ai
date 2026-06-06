import sys
import traceback
import yaml
import cv2

try:
    with open("/home/auto-calibration-ms/configs/config_AutoMagicCalib/mv_amc_config.yaml", "r") as f:
        cfg = yaml.safe_load(f)

    import core.camera_estimation.layout_alignment_post_process as lapp

    original_findHomography = cv2.findHomography

    def hooked_findHomography(*args, **kwargs):
        print(">>> cv2.findHomography called with:")
        print("  src points shape:", getattr(args[0], 'shape', 'No shape'))
        print("  dst points shape:", getattr(args[1], 'shape', 'No shape'))
        res = original_findHomography(*args, **kwargs)
        print("  Result type:", type(res[0]))
        if res[0] is None:
            print("  WARNING: findHomography returned None!")
            # Instead of returning None, let's return a dummy identity matrix to see if it bypasses the crash
            import numpy as np
            return np.eye(3), np.ones((len(args[0]), 1), dtype=np.uint8)
        return res

    cv2.findHomography = hooked_findHomography

    lapp.generate_transform_from_alignment_data(
        "/home/auto-calibration-ms/server/projects/project_20260528_032417_6056/output/alignment_data/alignment_data.json",
        "/home/auto-calibration-ms/server/projects/project_20260528_032417_6056/output/multi_view_results",
        cfg
    )
except Exception as e:
    print("Caught:", type(e), e)
    traceback.print_exc()
