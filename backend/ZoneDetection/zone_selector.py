"""
zone_selector.py
-----------------
Interactively mark a "restricted / not-allowed" region on a photo by
clicking points on it. The polygon you draw is saved to zone_config.json
so intrusion_detector.py can reuse it later.

Usage:
    python zone_selector.py --image path/to/photo.jpg --out zone_config.json

Controls:
    Left click   -> add a point to the polygon
    Right click  -> remove the last point
    'c'          -> close/finish the polygon
    's'          -> save the polygon to the output JSON file
    'r'          -> reset (clear all points)
    'q' / ESC    -> quit without saving
"""

import cv2
import json
import argparse
import os
import numpy as np

points = []
closed = False


def mouse_callback(event, x, y, flags, param):
    global points, closed
    if closed:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))
        print(f"Point added: ({x}, {y})  [total: {len(points)}]")
    elif event == cv2.EVENT_RBUTTONDOWN:
        if points:
            removed = points.pop()
            print(f"Removed point: {removed}")


def draw(img):
    display = img.copy()
    for i, p in enumerate(points):
        cv2.circle(display, p, 5, (0, 0, 255), -1)
        if i > 0:
            cv2.line(display, points[i - 1], p, (0, 255, 255), 2)

    if closed and len(points) > 2:
        cv2.line(display, points[-1], points[0], (0, 255, 255), 2)
        overlay = display.copy()
        cv2.fillPoly(overlay, [np.array(points, dtype=np.int32)], (0, 0, 255))
        display = cv2.addWeighted(overlay, 0.3, display, 0.7, 0)

    status = "CLOSED - press 's' to save" if closed else "OPEN - click to add points, 'c' to close"
    cv2.putText(display, status, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    return display


def main():
    global closed, points
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Path to the reference photo")
    parser.add_argument("--out", default="zone_config.json", help="Where to save the marked zone")
    args = parser.parse_args()

    img = cv2.imread(args.image)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {args.image}")

    win = "Mark restricted zone"
    cv2.namedWindow(win)
    cv2.setMouseCallback(win, mouse_callback)

    print("Left click: add point | Right click: undo | 'c': close polygon")
    print("'s': save | 'r': reset | 'q'/ESC: quit")

    while True:
        cv2.imshow(win, draw(img))
        key = cv2.waitKey(20) & 0xFF

        if key == ord('c'):
            if len(points) >= 3:
                closed = True
            else:
                print("Need at least 3 points to close the polygon.")
        elif key == ord('r'):
            points = []
            closed = False
            print("Reset.")
        elif key == ord('s'):
            if len(points) >= 3:
                config = {
                    "image": os.path.abspath(args.image),
                    "image_size": [img.shape[1], img.shape[0]],  # width, height
                    "polygon": points,
                }
                with open(args.out, "w") as f:
                    json.dump(config, f, indent=2)
                print(f"Saved restricted zone with {len(points)} points to {args.out}")
            else:
                print("Draw and close a polygon (>=3 points) before saving.")
        elif key in (ord('q'), 27):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
