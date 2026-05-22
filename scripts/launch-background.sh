#!/usr/bin/env bash

# WAJA Video Grabber — background launcher (no Terminal window)
# Called by the .app bundle. Logs to videograb/logs/

# Ensure Homebrew binaries (ffmpeg, git, etc.) are in PATH.
# .app bundles don't inherit the user's shell profile.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/launch.log"

exec > "$LOG_FILE" 2>&1
echo "=== WAJA Video Grabber starting at $(date) ==="

cd "$PROJECT_DIR"

# 1. Git pull (non-fatal)
if [ -d .git ]; then
  git pull --quiet 2>/dev/null || echo "⚠ Could not pull updates (offline?)."
fi

# 2. Activate venv
source "$PROJECT_DIR/venv/bin/activate"

# 3. Install any new dependencies
pip install -r requirements.txt --quiet 2>/dev/null

# 4. Update yt-dlp
pip install -U yt-dlp --quiet 2>/dev/null

# 5. Kill any existing server on port 8000
lsof -ti:8000 | xargs kill 2>/dev/null
sleep 0.5

# 6. Start server
uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"

# 7. Save PID so the app can stop it later
echo "$SERVER_PID" > "$LOG_DIR/server.pid"

# 8. Wait for server, then open browser
sleep 1.5
open "http://127.0.0.1:8000"

echo "=== WAJA Video Grabber running ==="

# Keep alive
wait "$SERVER_PID"
echo "=== Server stopped at $(date) ==="
