# ONE EYE — Industrial Safety Intelligence Platform
## Complete Engineering, Architecture & Context Guide for Future AI Agents & Developers

> **System Mission**:  
> *"ONE EYE is a real-time safety decision platform with AI vision inside it — not just a website with YOLO running behind it. It converts passive CCTV and mobile cameras into an active industrial hazard defense layer."*
>
> **Core Progression**:  
> **Detect ➔ Understand ➔ Assess ➔ Alert ➔ Prevent**  
> *(CCTV Watches → AI Sees → Tracking Remembers → Context Explains → Geometry Measures → Time Verifies → Risk Engine Decides → ONE EYE Prioritizes → Human Acts → System Verifies → Evidence Is Stored → Organization Learns)*

---

## Table of Contents
1. [Core Design Philosophy & Architectural Contract](#1-core-design-philosophy--architectural-contract)
2. [High-Level System Architecture & Dataflow](#2-high-level-system-architecture--dataflow)
3. [Deep Component Breakdown](#3-deep-component-breakdown)
   - [3.1 Edge Video Ingestion & Hardware Integration](#31-edge-video-ingestion--hardware-integration)
   - [3.2 Perception & Pose Layer](#32-perception--pose-layer)
   - [3.3 Multi-Object Tracking & Identity Continuity (ByteTrack)](#33-multi-object-tracking--identity-continuity-bytetrack)
   - [3.4 Spatial Homography & Zone Engine](#34-spatial-homography--zone-engine)
   - [3.5 Temporal Exposure & Persistence Engine](#35-temporal-exposure--persistence-engine)
   - [3.6 Compound 0–100 Risk Engine & Hard Rules](#36-compound-0100-risk-engine--hard-rules)
   - [3.7 Safety Event State Machine Lifecycle](#37-safety-event-state-machine-lifecycle)
   - [3.8 Multi-Channel Alert Dispatcher](#38-multi-channel-alert-dispatcher)
   - [3.9 Forensic Evidence Locker & Audit Trail](#39-forensic-evidence-locker--audit-trail)
   - [3.10 Next.js 14 Industrial Command Center](#310-nextjs-14-industrial-command-center)
4. [Critical Hardware & Platform Lessons (Gotchas for Future Agents)](#4-critical-hardware--platform-lessons-gotchas-for-future-agents)
5. [Port Allocations & Service Map](#5-port-allocations--service-map)
6. [Repository Directory Structure](#6-repository-directory-structure)
7. [Reference Project: himanshu_one_eye](#7-reference-project-himanshu_one_eye)
8. [Standard Development Workflows & Commands](#8-standard-development-workflows--commands)
9. [Future Roadmap & Next Steps](#9-future-roadmap--next-steps)

---

## 1. Core Design Philosophy & Architectural Contract

When building or modifying features in ONE EYE, future agents **MUST** uphold these non-negotiable architectural principles:

1. **The Operator Sees Decisions, Not Raw Math**:
   - The safety control room operator has seconds to act. Do not make them interpret bounding boxes or raw confidence scores. Surface **who is in danger, what machine they are near, the exact metric distance (e.g. `1.1m`), the continuous dwell time (e.g. `8.4s`), and the exact corrective action.**
2. **Decoupled Ingestion & Inference**:
   - Video ingestion streams at **30–60 FPS** without jitter. Heavy AI inference runs asynchronously in the background so video feeds never freeze.
3. **Compound Risk Over Single-Trigger Alarms**:
   - Risk is composite: $\text{Base Severity} + \text{Proximity Score} + \text{Exposure Score} + \text{Hazard Synergies}$.
   - Single-frame detections never trigger critical sirens; temporal debouncing confirms persistence.
4. **Failsafe Camera Health Reporting**:
   - If a camera stream degrades or disconnects, the system surfaces `CAMERA OFFLINE — SAFETY COVERAGE DEGRADED`.
5. **Passive Hardware Discovery**:
   - Never probe video capture devices in loops. Use OS-level metadata to prevent camera indicator light flashing or device cycling.

---

## 2. High-Level System Architecture & Dataflow

```mermaid
flowchart TD
    A[Industrial RTSP / IP Camera / Mobile USB / Web] --> B[Edge Ingestion Pipeline (30-60 FPS Unblocked)]
    B --> C[Asynchronous Frame Queue (15-20 FPS)]
    C --> D[YOLOv8 Object & Person Detector (Apple Silicon MPS / GPU)]
    C --> E[Fall & Posture Keypoint Detector]
    C --> F[Fire & Smoke Contour Engine]
    
    D & E --> G[ByteTrack Tracking (Worker #01, #02...)]
    G --> H[Foot-Anchor Ground Projection (Bottom-Center Bounding Box)]
    
    H --> I[3x3 Planar Homography Engine (Metric Distance in Meters)]
    H --> J[Shapely Polygon Restricted Zone Geofencing]
    
    I & J --> K[Temporal Exposure Engine (Dwell Time in Seconds)]
    K --> L[Compound Risk Engine (0-100 Score + Hard Safety Rules)]
    
    L --> M[Safety Event State Machine]
    M --> N{Status}
    N -->|DETECTED| O[Evaluating Dwell Cooldown]
    N -->|ALERTING| P[Multi-Channel Alert Dispatcher]
    N -->|ACKNOWLEDGED| Q[Operator Action Recorded]
    N -->|RESOLVED| R[Auto-Resolved & Logged to DB]
    
    P --> S[Next.js 14 Industrial Dashboard (WebSockets)]
    P --> T[Audio TTS / Siren Relays]
    P --> U[Forensic Evidence Locker (Annotated JPEG Snapshots)]
```

---

## 3. Deep Component Breakdown

### 3.1 Edge Video Ingestion & Hardware Integration
- **Files**: [`backend/app/cv/pipeline.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/cv/pipeline.py), [`backend/app/cv/source.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/cv/source.py), [`backend/app/cv/usb_mobile.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/cv/usb_mobile.py)
- **Mechanism**:
  - `CameraPipeline._run_loop`: Reads frames every 33ms (30 FPS), sets `self.latest_frame`.
  - `CameraPipeline._process_frame_async`: Evaluates YOLOv8 + ByteTrack + Proximity every 65ms (`_ai_interval`) in non-blocking background tasks with `_inference_in_flight` guards.
  - Video sources supported: RTSP streams, MP4 test videos, USB Webcams (UVC), and Mobile Browser WebSockets (`/ws/mobile-stream`).

### 3.2 Perception & Pose Layer
- **Files**: [`backend/app/cv/detector.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/cv/detector.py), [`backend/app/cv/fall.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/cv/fall.py), [`backend/app/cv/fire_smoke.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/cv/fire_smoke.py), [`backend/app/cv/ppe.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/cv/ppe.py)
- **Model**: `yolov8n.pt` accelerated via **Apple Silicon Metal Performance Shaders (`device = "mps"`)** on macOS and CUDA on Linux.
- **Tuned Threshold**: Confidence threshold calibrated to `0.25` for robust human detection in indoor, angled, and low-light conditions.

### 3.3 Multi-Object Tracking & Identity Continuity (ByteTrack)
- **File**: [`backend/app/cv/tracker.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/cv/tracker.py)
- **Mechanism**: Combines 2D Bounding Box Intersection-over-Union (IoU) with Centroid Euclidean distance cost matrices.
- **Foot-Anchor Ground Projection**: Instead of measuring from the bounding box center (which fluctuates as arms move), spatial coordinates use the **bottom-center point (`(x1 + x2)/2, y2`)** representing the worker's foot contact on the factory floor.

### 3.4 Spatial Homography & Zone Engine
- **Files**: [`backend/app/cv/homography.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/cv/homography.py), [`backend/app/cv/zones.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/cv/zones.py), [`backend/app/cv/proximity.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/cv/proximity.py)
- **Planar Homography**: $3 \times 3$ transformation matrix $H$ mapping camera perspective pixels $(u, v)$ to real-world ground meters $(X, Y)$.
- **Zone Geofencing**: Shapely polygon intersection checking if worker foot-anchors are inside hazardous machinery boundaries.

### 3.5 Temporal Exposure & Persistence Engine
- **File**: [`backend/app/cv/exposure.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/cv/exposure.py)
- Tracks continuous hazard dwell duration in seconds (`exposure_seconds`).
- Prevents alert fatigue: fleeting crossings (<1.5s) are evaluated as transients, while sustained dwell (>5s) escalates severity.

### 3.6 Compound 0–100 Risk Engine & Hard Rules
- **Files**: [`backend/app/risk/engine.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/risk/engine.py), [`backend/app/risk/thresholds.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/risk/thresholds.py)
- **Score Formula**:
  $$\text{Risk} = \min(100, \text{Base} + \text{Proximity Score} + \text{Duration Score} + \text{Synergy})$$
- **Synergies**:
  - `NO_HELMET` + `RESTRICTED_ZONE`: $+15$ bonus
  - `NO_PPE` + `CRITICAL_PROXIMITY`: $+20$ bonus
  - `WORKER_FALL` near active machine: $+25$ bonus
- **Hard Safety Rules**:
  - Confirmed Fire/Smoke $\rightarrow$ Instant **95 (CRITICAL)**
  - Confirmed Worker Fall $\rightarrow$ Instant **90 (CRITICAL)**
  - Active Machine Breach ($<0.8\text{m}$) $\rightarrow$ Instant **86 (CRITICAL)**

### 3.7 Safety Event State Machine Lifecycle
- **Files**: [`backend/app/events/state_machine.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/events/state_machine.py), [`backend/app/events/event_manager.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/events/event_manager.py)
- **Lifecycle States**:
  $$\text{MONITORING} \longrightarrow \text{DETECTED} \longrightarrow \text{EVALUATING} \longrightarrow \text{ALERTING} \longrightarrow \text{ACKNOWLEDGED} \longrightarrow \text{RESOLVED} \longrightarrow \text{LOGGED}$$
- Collision-free event identifiers: `EVT-YYYYMMDD-HHMMSS-XXXX`.

### 3.8 Multi-Channel Alert Dispatcher
- **File**: [`backend/app/alerts/dispatcher.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/alerts/dispatcher.py)
- Dispatches incidents over:
  1. **WebSocket Broadcast**: Pushes live JSON to connected dashboards in $<10\text{ms}$.
  2. **Text-To-Speech (TTS)**: Voice announcement for immediate floor alert.
  3. **Hardware Strobe/Siren Relays**: GPIO / IP relay interlock support.

### 3.9 Forensic Evidence Locker & Audit Trail
- **Files**: [`backend/app/cv/evidence.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/cv/evidence.py), [`backend/app/db/`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/db/)
- Automatically saves annotated JPEG snapshots to `evidence/YYYY/MM/DD/EVT-*.jpg` featuring bounding overlays, risk badges, worker IDs, and rule breakdowns.

### 3.10 Next.js 14 Industrial Command Center
- **Directory**: [`frontend/`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/frontend/)
- **Stack**: Next.js 14 App Router, Vanilla Tailwind CSS (Industrial Dark Mode theme), WebSocket hooks, HTML5 Canvas live video bounding overlay.
- **Key Tabs**:
  - `MonitoringArray.tsx`: Live camera grid with stream pause and widescreen focus.
  - `TopNavBar.tsx`: `LIVE MODE (PROD)` vs `DEMO SIMULATION` toggle, `AI SCANNING: ON / STANDBY` master switch.
  - `EventStreamSidebar.tsx`: Real-time priority-ordered active alert queue.
  - `ForensicDetailModal.tsx`: Incident inspection zoom, timeline, 1-click Acknowledge / Escalate / Resolve, and Operator Feedback (`Correct`, `False Alarm`, `Uncertain`).
  - `SafetyMapTab.tsx`: 2D plant map with active hazard beacons.
  - `AnalyticsTab.tsx`: Risk distributions, recurring breach analytics, response time metrics.

---

## 4. Critical Hardware & Platform Lessons (Gotchas for Future Agents)

### ⚠️ Gotcha 1: Camera Hardware Cycling / 30-Second Disconnect Loop
- **Problem**: Opening `cv2.VideoCapture(idx)` in background scanning loops and immediately calling `cap.release()` cuts hardware power on macOS and UVC webcams.
- **Rule**: **NEVER use `cv2.VideoCapture()` in background discovery loops.** Use passive OS metadata (`system_profiler SPCameraDataType` on macOS / `/sys/class/video4linux/` on Linux) in [`backend/app/cv/usb_mobile.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/cv/usb_mobile.py).

### ⚠️ Gotcha 2: Rapid Reconnect Hammering
- **Problem**: When a camera is offline, calling `connect()` on every 33ms frame loop locks the CPU and spams the USB bus.
- **Rule**: Always enforce the **4-second exponential reconnect cooldown** (`_last_reconnect_attempt`) in [`backend/app/cv/source.py`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/backend/app/cv/source.py).

### ⚠️ Gotcha 3: macOS AVFoundation Device Indices
- **Index `0`**: Built-in Mac FaceTime HD Camera.
- **Index `>= 1`**: External USB Webcams, Android UVC Webcams (Pixel 6a), or Continuity Cameras.

### ⚠️ Gotcha 4: Live Mode vs Demo Mode
- `DEMO_MODE=False` in `config.py` runs 100% on live physical camera streams.
- `DEMO_MODE=True` exposes the 5 interactive demo scenario cards on the top navbar for presentations and synthetic testing.

---

## 5. Port Allocations & Service Map

| Port | Service | Technology | Running Command |
|---|---|---|---|
| **`8001`** | **ONE EYE Backend API & CV Engine** | FastAPI, Uvicorn, WebSockets, PyTorch MPS | `cd backend && ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001` |
| **`3001`** | **ONE EYE Frontend Command Center** | Next.js 14 Production Server | `cd frontend && npm start` |
| **`8005`** | **Himanshu One_Eye Reference Web API** | FastAPI, YOLOv8, Qwen-VL, Rules JSON | `cd himanshu_one_eye && ../.venv/bin/uvicorn server:app --host 0.0.0.0 --port 8005` |

---

## 6. Repository Directory Structure

```
One_Eye/
├── backend/                        # FastAPI + PyTorch Computer Vision Backend
│   ├── app/
│   │   ├── alerts/                 # Multi-channel notification dispatcher
│   │   ├── api/                    # REST API endpoints (cameras, events, zones, health)
│   │   ├── cv/                     # Computer vision pipelines (YOLO, ByteTrack, Zones, Homography)
│   │   ├── db/                     # SQLAlchemy async models and SQLite/PostgreSQL repositories
│   │   ├── events/                 # Safety event state machine and lifecycle manager
│   │   ├── reasoning/              # VLM ambiguity reasoner interface (Qwen3-VL)
│   │   ├── risk/                   # 0-100 Compound Risk Calculation Engine
│   │   ├── websocket/              # Real-time WebSocket connection manager
│   │   ├── config.py               # Central backend configuration & environment settings
│   │   └── main.py                 # FastAPI application bootstrap & route registration
│   └── requirements.txt            # Python dependencies
├── frontend/                       # Next.js 14 Industrial Safety Command Center
│   ├── app/                        # App router (page.tsx, layout.tsx, globals.css)
│   ├── components/dashboard/       # Industrial UI panels, live grid, alert queue, modals
│   ├── lib/                        # API client (api.ts) and WebSocket live hook (websocket.ts)
│   ├── types/                      # TypeScript definitions (SafetyEvent, Camera, Zone, Track)
│   └── package.json                # Frontend npm scripts and dependencies
├── himanshu_one_eye/               # Cloned Reference Project (Tkinter + Qwen Ollama)
├── scripts/                        # Benchmarking, synthetic video generation, demo seeders
├── evidence/                       # Forensic annotated JPEG snapshots (auto-generated)
├── .gitignore                      # Clean exclusions (node_modules, .venv, *.db, cache)
├── PRODUCTION_PLAN.md              # 60-point Master Engineering Blueprint
├── PROJECT_KNOWLEDGE_BASE.md       # This exhaustive developer & AI agent context guide
└── README.md                       # High-level overview & setup instructions
```

---

## 7. Reference Project: `himanshu_one_eye`

The repository `https://github.com/himanshudubey159/One_eye.git` is cloned locally in [`himanshu_one_eye/`](file:///Users/vaibhavkrishnakesarwani/Desktop/One_Eye/himanshu_one_eye).
- **Core modules**: `main.py` (Tkinter GUI), `server.py` (FastAPI Web GUI on port 8005), `qwen.py` (Ollama Qwen-VL prompt engine), `rule_engine.py`, `zones.py`, `database.py`, `rules.json`.
- **How to run the web server**:
  ```bash
  cd himanshu_one_eye && ../.venv/bin/uvicorn server:app --host 0.0.0.0 --port 8005
  ```
- **How to run the desktop GUI**:
  ```bash
  cd himanshu_one_eye && ../.venv/bin/python main.py
  ```

---

## 8. Standard Development Workflows & Commands

### 1. Starting the Entire Stack
```bash
# Terminal 1: Backend
cd backend && ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001

# Terminal 2: Frontend
cd frontend && npm start  # (or npm run dev for hot-reloading)
```

### 2. Building Frontend Production Bundle
```bash
cd frontend && npm run build
```

### 3. Running Backend Tests & Latency Benchmark
```bash
# Run unit & integration tests
cd backend && ../.venv/bin/pytest tests/ -v

# Run performance benchmark
.venv/bin/python scripts/benchmark.py
```

### 4. Git Repository & Remote
- **GitHub URL**: `https://github.com/Vkkthebest2004/One_Eye`
- **Branch**: `main`

---

## 9. Future Roadmap & Next Steps

When coding the next set of features, follow these milestones:
1. **Interactive In-Browser Polygon Zone Drawing**: Allow operators to click on the live stream canvas in `SafetyMapTab.tsx` / `CalibrationTool.tsx` to save polygon zones directly into SQLite/PostgreSQL.
2. **Ground-Plane 4-Point Homography Wizard**: Provide an interactive tool on the live camera stream to pick 4 floor points and compute metric conversion coefficients.
3. **Audio Speech Output Toggle**: Add a volume/mute switch in the top navbar for Sarvam/macOS TTS hazard announcements.
4. **Enhanced PPE Sub-Classifiers**: Integrate fine-tuned hardhat and reflective vest classifier heads into the tracking pipeline.
