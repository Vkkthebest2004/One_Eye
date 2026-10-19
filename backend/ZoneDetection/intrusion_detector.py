"""
intrusion_detector.py
----------------------
Detects whether a hand enters a "restricted / not-allowed" zone that you
marked earlier with zone_selector.py.

It uses MediaPipe Hands to find hand landmarks in each frame, then checks
whether any landmark falls inside the marked polygon using
cv2.pointPolygonTest. If it does, an on-screen alert is raised and a
snapshot is saved.

Usage examples:
    # Live webcam
    python intrusion_detector.py --zone zone_config.json --source 0

    # Video file
    python intrusion_detector.py --zone zone_config.json --source path/to/video.mp4

    # Single image
    python intrusion_detector.py --zone zone_config.json --source path/to/photo.jpg --image-mode
"""

import cv2
import json
import argparse
import time
import os
import numpy as np
import mediapipe as mp

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils


def load_zone(path):
    with open(path, "r") as f:
        cfg = json.load(f)
    return cfg


def scale_polygon(polygon, from_size, to_size):
    """Rescale the polygon if the current frame size differs from the size
    of the image the zone was originally marked on."""
    fw, fh = from_size
    tw, th = to_size
    if (fw, fh) == (tw, th):
        return polygon
    sx, sy = tw / fw, th / fh
    return [(int(x * sx), int(y * sy)) for x, y in polygon]


def point_in_zone(point, polygon):
    poly_np = np.array(polygon, dtype=np.int32)
    return cv2.pointPolygonTest(poly_np, point, False) >= 0


def draw_zone(frame, polygon, intruded):
    overlay = frame.copy()
    color = (0, 0, 255) if intruded else (0, 255, 0)
    poly_np = np.array(polygon, dtype=np.int32)
    cv2.fillPoly(overlay, [poly_np], color)
    frame = cv2.addWeighted(overlay, 0.25, frame, 0.75, 0)
    cv2.polylines(frame, [poly_np], True, color, 2)
    return frame


def process_frame(frame, hands, polygon, save_dir=None):
    h, w = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    intruded = False
    intrusion_points = []

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            for lm in hand_landmarks.landmark:
                px, py = int(lm.x * w), int(lm.y * h)
                if point_in_zone((px, py), polygon):
                    intruded = True
                    intrusion_points.append((px, py))

    frame = draw_zone(frame, polygon, intruded)

    for p in intrusion_points:
        cv2.circle(frame, p, 8, (0, 0, 255), -1)

    if intruded:
        cv2.putText(frame, "INTRUSION DETECTED - RESTRICTED ZONE TOUCHED",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
            fname = os.path.join(save_dir, f"intrusion_{int(time.time()*1000)}.jpg")
            cv2.imwrite(fname, frame)

    return frame, intruded


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zone", required=True, help="Path to zone_config.json from zone_selector.py")
    parser.add_argument("--source", default="0", help="Webcam index, video path, or image path")
    parser.add_argument("--image-mode", action="store_true", help="Treat --source as a single still image")
    parser.add_argument("--save-dir", default="intrusions", help="Where to save snapshots of detected intrusions")
    args = parser.parse_args()

    cfg = load_zone(args.zone)
    original_polygon = [tuple(p) for p in cfg["polygon"]]
    original_size = tuple(cfg["image_size"])

    hands = mp_hands.Hands(
        static_image_mode=args.image_mode,
        max_num_hands=2,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.5,
    )

    if args.image_mode:
        frame = cv2.imread(args.source)
        if frame is None:
            raise FileNotFoundError(f"Could not load image: {args.source}")
        h, w = frame.shape[:2]
        polygon = scale_polygon(original_polygon, original_size, (w, h))
        frame, intruded = process_frame(frame, hands, polygon, args.save_dir)
        print("INTRUSION DETECTED" if intruded else "No intrusion detected")
        cv2.imshow("Intrusion Detection", frame)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        return

    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video source: {args.source}")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        h, w = frame.shape[:2]
        polygon = scale_polygon(original_polygon, original_size, (w, h))
        frame, _ = process_frame(frame, hands, polygon, args.save_dir)
        cv2.imshow("Intrusion Detection (press 'q' to quit)", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
