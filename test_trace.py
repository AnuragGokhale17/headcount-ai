import sys
import traceback

def trace_calls(frame, event, arg):
    if event == "exception":
        exc_type, exc_value, exc_traceback = arg
        if exc_type is TypeError and "'NoneType' object is not subscriptable" in str(exc_value):
            print("EXCEPTION CAUGHT IN TRACE!")
            print("Function:", frame.f_code.co_name)
            print("Locals:")
            for k, v in frame.f_locals.items():
                print(f"  {k}: {type(v)} = {str(v)[:100]}")
    return trace_calls

sys.settrace(trace_calls)

try:
    from core.camera_estimation.layout_alignment_post_process import generate_transform_from_alignment_data
    generate_transform_from_alignment_data(
        "/home/auto-calibration-ms/server/projects/project_20260528_032417_6056/output/alignment_data/alignment_data.json",
        "/home/auto-calibration-ms/server/projects/project_20260528_032417_6056/output/multi_view_results",
        "/home/auto-calibration-ms/configs/config_AutoMagicCalib/mv_amc_config.yaml"
    )
except Exception as e:
    print("Caught:", type(e), e)
    traceback.print_exc()

sys.settrace(None)
