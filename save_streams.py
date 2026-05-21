import subprocess
import time
import datetime
import os

# ---------------- CONFIG ---------------- #
RTSP_STREAMS = {
    "cam1": "rtsp://admin:admin123@10.0.13.150:554/cam/realmonitor?channel=1&subtype=0",
    "cam2": "rtsp://admin:admin123@10.0.13.151:554/cam/realmonitor?channel=1&subtype=0",
    "cam3": "rtsp://admin:admin123@10.0.13.152:554/cam/realmonitor?channel=1&subtype=0",
    # "cam5": "rtsp://user:pass@192.168.1.105:554/stream1",
}

DURATION_SECONDS = 60
OUTPUT_DIR = "recordings"
# ---------------------------------------- #

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Align to next full minute (HH:MM:00)
now = datetime.datetime.now()
start_time = (now + datetime.timedelta(minutes=1)).replace(second=0, microsecond=0)

print(f"Recording will start at: {start_time}")

# Wait until start time
while datetime.datetime.now() < start_time:
    time.sleep(0.1)

print("Starting recording...")

processes = []

timestamp_str = start_time.strftime("%Y%m%d_%H%M%S")

for cam_name, rtsp_url in RTSP_STREAMS.items():
    output_file = os.path.join(
        OUTPUT_DIR, f"{cam_name}_{timestamp_str}.mp4"
    )

    cmd = [
        "ffmpeg",
        "-rtsp_transport", "tcp",
        "-i", rtsp_url,
        "-t", str(DURATION_SECONDS),
        "-c", "copy",            # no re-encoding (fast + no frame loss)
        "-y",
        output_file
    ]

    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    processes.append(p)

# Wait for all recordings to finish
for p in processes:
    p.wait()

print("✅ All cameras recorded successfully")