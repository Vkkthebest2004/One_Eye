#!/usr/bin/env bash
# ONE EYE — Production-Grade Low-Resource Startup Script
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "=================================================="
echo "👁️  ONE EYE — Industrial Safety Intelligence Platform"
echo "=================================================="

# Ensure ports 8000 and 3001 are free
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
lsof -ti :3001 | xargs kill -9 2>/dev/null || true

# Apply Thread and Resource Limiters for Apple Silicon / Edge CPU
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0

echo "[1/2] Starting Optimized Backend Service (port 8001)..."
cd "$DIR/backend"
"$DIR/.venv/bin/uvicorn" app.main:app --host 0.0.0.0 --port 8001 --workers 1 &
BACKEND_PID=$!

echo "[2/2] Starting Frontend Service (port 3001)..."
cd "$DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo "=================================================="
echo "✅ ONE EYE is online!"
echo "📍 Landing Page:    http://localhost:3001/"
echo "📍 Safety Console:  http://localhost:3001/dashboard"
echo "📍 Mobile Sentry:   http://localhost:3001/mobile-cam"
echo "📍 Backend API:     http://localhost:8000/api/health"
echo "=================================================="

wait $BACKEND_PID $FRONTEND_PID
