import sys
import traceback
import yaml
import cv2

try:
    with open("/home/auto-calibration-ms/configs/config_AutoMagicCalib/mv_amc_config.yaml", "r") as f:
        cfg = yaml.safe_load(f)

    import core.camera_estimation.layout_alignment_post_process as lapp

    original_triangulatePoints = cv2.triangulatePoints

    def hooked_triangulatePoints(*args, **kwargs):
        print(">>> cv2.triangulatePoints called!")
        res = original_triangulatePoints(*args, **kwargs)
        return res

    cv2.triangulatePoints = hooked_triangulatePoints

    lapp.generate_transform_from_alignment_data(
        "/home/auto-calibration-ms/server/projects/project_20260528_032417_6056/output/alignment_data/alignment_data.json",
        "/home/auto-calibration-ms/server/projects/project_20260528_032417_6056/output/multi_view_results",
        cfg
    )
except Exception as e:
    print("Caught:", type(e), e)
    traceback.print_exc()
