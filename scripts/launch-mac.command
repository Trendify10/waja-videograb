#!/usr/bin/env bash

# WAJA Video Grabber Launcher
# Double-click this file (or the Desktop shortcut) to start WAJA Video Grabber.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# 1. Git pull (non-fatal if offline or not a repo)
if [ -d .git ]; then
  echo "Checking for updates..."
  git pull --quiet 2>/dev/null || echo "⚠ Could not pull updates (offline?). Continuing with current version."
fi

# 2. Activate venv
source "$PROJECT_DIR/venv/bin/activate"

# 3. Install any new dependencies (quiet)
pip install -r requirements.txt --quiet 2>/dev/null

# 4. Update yt-dlp (quiet)
pip install -U yt-dlp --quiet 2>/dev/null

# 5. Start server in background
echo "Starting WAJA Video Grabber..."
uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
SERVER_PID=$!

# 6. Wait briefly for server to start, then open browser
sleep 1.5
open "http://127.0.0.1:8000"

echo "WAJA Video Grabber is running at http://127.0.0.1:8000"
echo "Close this window or press Ctrl+C to stop."

# 7. Clean shutdown on exit
cleanup() {
  echo ""
  echo "Shutting down WAJA Video Grabber..."
  kill "$SERVER_PID" 2>/dev/null
  wait "$SERVER_PID" 2>/dev/null
  echo "Goodbye!"
}
trap cleanup EXIT INT TERM

# Keep script alive until server dies or user closes
wait "$SERVER_PID"
