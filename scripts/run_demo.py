import os
import sys
import subprocess
import uvicorn
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.config import settings

def main():
    print("=" * 70)
    print("  🚀 STARTING ONE EYE INDUSTRIAL SAFETY INTELLIGENCE PLATFORM")
    print("  Mode: DEMO / LOCAL")
    print("  API Docs: http://localhost:8000/docs")
    print("  WebSocket: ws://localhost:8000/ws")
    print("=" * 70)

    # Ensure demo video and seed database exist
    video_path = Path("./videos/demo/factory_safety.mp4")
    if not video_path.exists():
        print("Generating synthetic demo video...")
        subprocess.run([sys.executable, "scripts/generate_demo_video.py"], check=True)

    print("Checking database seed...")
    subprocess.run([sys.executable, "scripts/seed_demo.py"], check=True)

    print("\nLaunching FastAPI Backend on http://0.0.0.0:8000 ...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        app_dir=str(backend_path)
    )

if __name__ == "__main__":
    main()
