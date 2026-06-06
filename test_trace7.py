import sys
import traceback
import yaml

try:
    with open("/home/auto-calibration-ms/configs/config_AutoMagicCalib/mv_amc_config.yaml", "r") as f:
        cfg = yaml.safe_load(f)

    import core.camera_estimation.layout_alignment_post_process as lapp

    original_get_transform = lapp.get_transform_from_cam0_to_layout

    def hooked_get_transform(alignment_data, proj_mat0, proj_mat1):
        print("--- HOOKED get_transform_from_cam0_to_layout ---")
        print("alignment_data length:", len(alignment_data))
        if len(alignment_data) > 0:
            print("First item in alignment_data:", alignment_data[0])
            print("First item length:", len(alignment_data[0]))
            if len(alignment_data[0]) > 0:
                print("First sub-item type:", type(alignment_data[0][0]))
        return original_get_transform(alignment_data, proj_mat0, proj_mat1)

    lapp.get_transform_from_cam0_to_layout = hooked_get_transform

    lapp.generate_transform_from_alignment_data(
        "/home/auto-calibration-ms/server/projects/project_20260528_032417_6056/output/alignment_data/alignment_data.json",
        "/home/auto-calibration-ms/server/projects/project_20260528_032417_6056/output/multi_view_results",
        cfg
    )
except Exception as e:
    print("Caught:", type(e), e)
    traceback.print_exc()
