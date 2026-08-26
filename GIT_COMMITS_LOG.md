# 📜 ONE EYE — Git Commit History & Recovery Log

This document tracks all version-controlled milestones in the repository. If you ever need to inspect or revert to a specific working state, you can use the commands listed below.

---

## Milestone Log

- **Commit `7ed025a`**: `feat(pose): integrate YOLOv8-pose keypoint ankle ground localization and Euclidean distance tracking`
  - Integrated `yolov8n-pose.pt` keypoint estimation to extract human ankle joints (COCO kpt 15 & 16) for ground-truth millimeter-accurate foot contact coordinate determination.
  - Added mathematical Euclidean polygon distance calculation with Shapely geometry to compute sub-pixel proximity to danger zones.

- **Commit `32ae3ca`**: `feat(zones): implement precise coordinate-based fixed danger zone system with DANGER_ZONE_REACHED alerts`
  - Built precision coordinate-based fixed danger zone system with real-time vertex coordinates table ($P_1, P_2, \dots$), 2-click box mode, and multi-point polygon drawer.
  - Locked danger perimeter to fixed normalized $(X, Y)$ coordinates ($0.0000 - 1.0000$).
  - Configured `DANGER_ZONE_REACHED` alert trigger: only fires when a person's physical foot contact point enters the marked coordinate perimeter.

- **Commit `771a369`**: `feat(qwen-vl): enable all-object perception and dynamic hazard zone bounding`
  - Upgraded Qwen2-VL visual prompt and spatial grounding to detect all industrial entities: workers (`PERSON`), dangerous equipment (`MACHINE`), mobile equipment (`VEHICLE`), environmental hazards (`HAZARD_OBJECT`), and restricted areas (`DANGER_ZONE`).
  - Added automatic danger perimeter bounding: when hazardous machinery or danger zones are recognized, the system dynamically generates safety perimeters and tracks worker contact breaches.

- **Commit `44cbc34`**: `perf(cv): unlock 30 FPS inference by removing global serial lock and optimizing frame interval`
  - Unlocked 25–30+ FPS real-time surveillance by eliminating the global inference lock across camera channels.
  - Enabled concurrent asynchronous thread execution for YOLOv8s and Qwen2-VL inference.
  - Increased `INFERENCE_FPS = 30` and pipeline target frame interval to 33ms.

- **Commit `1da1b30`**: `fix(zones): resolve danger zone false breaches with strict foot ground-anchor intersection and mobile dynamic deactivation`
  - Fixed root cause of false danger zone breaches: replaced full bounding-box intersection with strict ground-contact foot anchor point-in-polygon verification.
  - Eliminated phantom static screen overlays on mobile feeds: all mobile zones are strictly dynamic and only activate when RANSAC homography matches the physical keyframe (`is_visible == True`).
  - Upgraded `QwenReasoner` to generate rich, contextual ambiguity descriptions explaining worker clearance, posture, and required corrective actions.
  - Cleaned up stale database test zones from `oneeye.db`.

## 📌 Commit Log Table

| Commit Hash | Component | Summary / Milestone Description |
| :--- | :--- | :--- |
| **`1da1b30`** | `zones` | Resolve danger zone false breaches with strict foot ground-anchor intersection |
| **`5dbae5e`** | `cv` | Integrate Qwen2-VL perception engine with hot-switching and precision person filtering |
| **`001497f`** | `perception` | Set Qwen2-VL as permanent default vision engine with high-throughput processing |
| **`7b0d2bf`** | `mobile` | Continuous auto-scan by default & unauthorized device badge detection |
| **`f77475c`** | `mobile-cam` | Progressive constraint cascade for rear & front sensors without OverconstrainedError |
| **`4bc40d1`** | `release` | Complete release build, tests, and configuration sync |
| **`6da95d7`** | `mobile` | Preserve USB ADB device registrations & add Direct USB Stream action button |
| **`83680c2`** | `visual-anchor` | True dynamic homography lock on physical object, out-of-view zone culling, & direct snapshot binding |
| **`2e62991`** | `safety-engine` | Multi-point zone intersection, resilient visual tracking fallback, eliminate false alarms, live mobile HUD |
| **`fd9560d`** | `docs` | Update commit log with visual memory milestone |
| **`15ae073`** | `visual-memory` | Planar Homography danger tracking, world-anchored visual memory, & mobile photo marker |
| **`8be1ca8`** | `docs` | Add comprehensive git commits log & failsafe recovery guide (`GIT_COMMITS_LOG.md`) |
| **`c096cbb`** | `mobile` | Consolidate single mobile camera channel (`CAM_MOBILE`) & robust sensor initialization |
| **`5864496`** | `cameras` | Fix real-time frame generator for mobile stream to prevent stalling |
| **`9441f08`** | `perception` | Shared model cache singleton for ultra-low latency multi-channel inference |
| **`436da4a`** | `perception` | Upgrade to YOLOv8s perception engine with hardware MPS acceleration |
| **`f9c27d5`** | `zones` | Direct crisp JPEG snapshot capture & persistent forbidden zone memory |
| **`bffedc9`** | `zones` | Remove default pixel perimeter, add live photo freeze & custom forbidden area marker |
| **`c014c4b`** | `mobile-cam` | Add hardware camera sensor selector dropdown & exact lens resolution |
| **`67288e5`** | `pipeline` | Prevent premature offline state & route live frames directly into pipelines |
| **`8966bd0`** | `mobile-cam` | Add dedicated Rear and Front camera selector buttons & deviceId binding |
| **`33116a6`** | `mobile-cam` | Force exact rear/back camera sensor selection & multi-tier device enumeration |
| **`38af0fc`** | `perception` | Eliminate ghost worker false positives with precision threshold & enable front camera flip |
| **`6ed48fd`** | `dashboard` | Auto-scan & enumerate ADB mobile devices on startup and page load |
| **`7564224`** | `mobile-cam` | Immediate stream & WebSocket activation on Enable Camera tap |
| **`419bf99`** | `rtsp` | Implement low-latency FFmpeg RTSP ingestion engine & direct RTSP connection UI |
| **`18d2a5d`** | `pipeline` | Seed full 6-channel CCTV & mobile surveillance array with synthetic streams |
| **`7d7dce7`** | `mobile` | Universal frame routing across all device serial keys & camera stream fallbacks |
| **`98b123b`** | `websocket` | Add `NumpySafeJSONEncoder` to prevent serialization drops on live detection updates |
| **`54a2e02`** | `mobile` | Prevent intent reload loops on phone & add numpy standby stream rendering |
| **`3ae6f44`** | `frontend` | Eliminate stream error reload loop & stabilize WebSocket connection |
| **`06e846c`** | `mobile` | Resolve pipeline registration, MultiTracker alias, & live mobile video streaming |
| **`d448f40`** | `cv` | Disable UVC hardware capture to strictly prevent host laptop webcam activation |
| **`6057753`** | `mobile` | Add Direct USB Web Stream mode with ADB reverse port tunneling |
| **`8be3ffa`** | `ui` | Production-grade terminology across navigation, KPIs, and surveillance array |
| **`255b284`** | `zones` | Interactive 2D No-Entry polygon editor with normalized SVG drawing |

---

## 🛠️ How to Revert or Switch to Any Previous Commit

### 1. View Current Status
```bash
git status
git log --oneline -n 10
```

### 2. Temporarily Switch to a Previous Commit (Read-Only Exploration)
To test an earlier commit without losing your current work:
```bash
git checkout <COMMIT_HASH>
# Example: git checkout 38af0fc
```

### 3. Return to Latest Main Branch
```bash
git checkout main
```

### 4. Hard Reset to a Specific Commit (Discards subsequent commits)
> ⚠️ *Only do this if you want to permanently roll back to that state.*
```bash
git reset --hard <COMMIT_HASH>
git push origin main --force
```
