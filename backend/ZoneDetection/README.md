# Restricted Zone Intrusion Detector

Mark a "not allowed" area on a photo, then automatically detect when a hand
enters that area — from a live webcam, a video file, or another photo.

## Setup

```bash
pip install -r requirements.txt
```

(You need Python 3.8–3.11 for best MediaPipe compatibility.)

## Step 1 — Mark the restricted zone

Run this on a reference photo of the place (e.g. a machine panel, an exhibit,
a control switch, a shelf):

```bash
python zone_selector.py --image reference_photo.jpg --out zone_config.json
```

- **Left click** on the photo to place points around the area you want to
  protect (you can trace any shape, not just a rectangle).
- **Right click** to undo the last point.
- Press **`c`** once you've placed at least 3 points, to close the polygon.
- Press **`s`** to save it to `zone_config.json`.
- Press **`q`** to quit.

## Step 2 — Run detection

**Live webcam:**
```bash
python intrusion_detector.py --zone zone_config.json --source 0
```

**A video file:**
```bash
python intrusion_detector.py --zone zone_config.json --source clip.mp4
```

**A single photo:**
```bash
python intrusion_detector.py --zone zone_config.json --source suspect_photo.jpg --image-mode
```

Whenever any hand-landmark point lands inside your marked polygon, the
zone turns red, an "INTRUSION DETECTED" banner appears on screen, and a
snapshot is auto-saved into the `intrusions/` folder with a timestamp.

## Notes / things you can tune

- `--save-dir` changes where alert snapshots are saved.
- The zone is stored as pixel coordinates + the original image size, and is
  automatically rescaled if you run detection on a different resolution
  (e.g. webcam at 1280x720 vs. the photo you marked at 1920x1080).
- Currently detects **hands** (MediaPipe Hands). If you also want to flag a
  person's whole body getting close (not just their hand), swap in
  `mediapipe.solutions.pose` the same way — same point-in-polygon logic
  applies to any (x, y) landmark.
- Detection confidence thresholds (`min_detection_confidence`,
  `min_tracking_confidence` in `intrusion_detector.py`) can be raised/lowered
  depending on how sensitive you want it to be.
