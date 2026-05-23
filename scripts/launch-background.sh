#!/usr/bin/env bash

# WAJA Video Grabber — background launcher (no Terminal window)
# Called by the .app bundle. Logs to videograb/logs/
#
# Smart behavior:
#   - If the server is already running, just open the browser.
#   - If not, start the server, then open the browser.

# Ensure Homebrew binaries (ffmpeg, git, etc.) are in PATH.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/launch.log"
PID_FILE="$LOG_DIR/server.pid"

open_browser() {
  open "http://127.0.0.1:8000"
}

# Check if server is already running
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    # Server is already running — just open the browser
    open_browser
    exit 0
  else
    # Stale PID file
    rm -f "$PID_FILE"
  fi
fi

# Also check if something else is on port 8000
if lsof -ti:8000 >/dev/null 2>&1; then
  lsof -ti:8000 | xargs kill 2>/dev/null
  sleep 0.5
fi

# From here on, log to file
exec > "$LOG_FILE" 2>&1
echo "=== WAJA Video Grabber starting at $(date) ==="

cd "$PROJECT_DIR"

# 1. Git pull (non-fatal)
if [ -d .git ]; then
  git pull --quiet 2>/dev/null || echo "Could not pull updates (offline?). Continuing."
fi

# 2. Activate venv
source "$PROJECT_DIR/venv/bin/activate"

# 3. Install any new dependencies
pip install -r requirements.txt --quiet 2>/dev/null

# 4. Update yt-dlp
pip install -U yt-dlp --quiet 2>/dev/null

# 5. Start server
uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"
echo "$SERVER_PID" > "$PID_FILE"

# 6. Wait for server, then open browser
sleep 1.5
open "http://127.0.0.1:8000"

echo "=== WAJA Video Grabber running ==="

# Keep alive until server exits
wait "$SERVER_PID"
rm -f "$PID_FILE"
echo "=== Server stopped at $(date) ==="
