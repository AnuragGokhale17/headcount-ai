import sys
import traceback
import yaml

def trace_calls(frame, event, arg):
    if event == "exception":
        exc_type, exc_value, exc_traceback = arg
        if exc_type is TypeError and "'NoneType' object is not subscriptable" in str(exc_value):
            print("EXCEPTION CAUGHT IN TRACE!")
            print("Function:", frame.f_code.co_name)
            print("Locals:")
            for k, v in frame.f_locals.items():
                try:
                    val_str = str(v)[:200]
                except:
                    val_str = "Error printing"
                print(f"  {k}: {type(v)} = {val_str}")
    return trace_calls

sys.settrace(trace_calls)

try:
    with open("/home/auto-calibration-ms/configs/config_AutoMagicCalib/mv_amc_config.yaml", "r") as f:
        cfg = yaml.safe_load(f)

    from core.camera_estimation.layout_alignment_post_process import generate_transform_from_alignment_data
    generate_transform_from_alignment_data(
        "/home/auto-calibration-ms/server/projects/project_20260528_032417_6056/output/alignment_data/alignment_data.json",
        "/home/auto-calibration-ms/server/projects/project_20260528_032417_6056/output/multi_view_results",
        cfg
    )
except Exception as e:
    print("Caught:", type(e), e)
    traceback.print_exc()

sys.settrace(None)
