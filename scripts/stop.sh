#!/usr/bin/env bash
# ONE EYE — Service Shutdown Script
set -e

echo "Shutting down ONE EYE services..."
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
lsof -ti :3001 | xargs kill -9 2>/dev/null || true
echo "✅ All ONE EYE services stopped."
