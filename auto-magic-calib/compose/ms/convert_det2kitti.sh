#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

echo $1
# Convert to absolute path to avoid relative path issues
target_dir=$(realpath "$1")
chown $(id -u):$(id -g) "$target_dir"
cd "$target_dir"
mkdir -p kitti_detector/Stream_0
mv kitti_detector/00_000* kitti_detector/Stream_0/. || true
cd $OLDPWD

SCRIPT_ROOT="$(dirname "$0")"

bash $SCRIPT_ROOT/kittiDetect2mot_4_viz.sh \
    -i "$target_dir/kitti_detector/Stream_0" \
    -o "$target_dir/Det-Stream_0.log.raw"

# Detect image resolution from rectified.jpg if it exists, otherwise fallback to 1920x1080
IMG_FILE="$target_dir/rectified.jpg"
if [ -f "$IMG_FILE" ]; then
    # Use python to get image size
    RES=$(python3 -c "from PIL import Image; img = Image.open('$IMG_FILE'); print(f'{img.width} {img.height}')" 2>/dev/null)
    IMG_W=$(echo $RES | awk '{print $1}')
    IMG_H=$(echo $RES | awk '{print $2}')
fi

# Fallback values
IMG_W=${IMG_W:-1920}
IMG_H=${IMG_H:-1080}

echo "Clipping detections to resolution: ${IMG_W}x${IMG_H}"

# Patch the MOT log to ensure bounding box x,y centers stay within image bounds
# MOT format: frame, id, bb_left, bb_top, bb_width, bb_height, conf, x, y, z
awk -F',' -v w="$IMG_W" -v h="$IMG_H" 'OFS="," {
    # limit left and width
    if ($3 < 0) { $5 = $5 + $3; $3 = 0 }
    if ($3 >= w) $3 = w - 1
    if ($3 + $5 > w) $5 = w - $3 - 0.1
    
    # limit top and height
    if ($4 < 0) { $6 = $6 + $4; $4 = 0 }
    if ($4 >= h) $4 = h - 1
    if ($4 + $6 > h) $6 = h - $4 - 0.1

    # ensure reasonable width/height
    if ($5 < 1) $5 = 1
    if ($6 < 1) $6 = 1
    
    # Dynamic clipping: nudge centers that land exactly on boundaries
    cx = $3 + $5 / 2.0;
    if (cx >= w) {
        $3 = w - 1.0 - ($5 / 2.0);
    } else if (cx >= 1.0 && cx % 1.0 == 0) {
        $3 = $3 - 0.1;
    }
    
    cy = $4 + $6 / 2.0;
    if (cy >= h) {
        $4 = h - 1.0 - ($6 / 2.0);
    } else if (cy >= 1.0 && cy % 1.0 == 0) {
        $4 = $4 - 0.1;
    }
    
    print $1,$2,$3,$4,$5,$6,$7,$8,$9,$10
}' "$target_dir/Det-Stream_0.log.raw" > "$target_dir/Det-Stream_0.log"

cp "$target_dir/Det-Stream_0.log" "$target_dir/Det-bboxes.log"
