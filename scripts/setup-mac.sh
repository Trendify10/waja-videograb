#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== WAJA Video Grabber Setup ==="
echo ""

# 1. Check / install Python 3.11+
PYTHON=""
for candidate in python3.13 python3.12 python3.11; do
  if command -v "$candidate" &>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done

if [ -z "$PYTHON" ]; then
  echo "Python 3.11+ not found. Installing via Homebrew..."
  if ! command -v brew &>/dev/null; then
    echo "ERROR: Homebrew is required. Install it from https://brew.sh"
    exit 1
  fi
  brew install python@3.12
  PYTHON="python3.12"
fi

PY_VERSION=$("$PYTHON" --version 2>&1)
echo "✓ Using $PY_VERSION"

# 2. Create virtual environment
echo "Creating virtual environment..."
"$PYTHON" -m venv "$PROJECT_DIR/venv"
echo "✓ Virtual environment created"

# 3. Install Python dependencies
echo "Installing Python dependencies..."
"$PROJECT_DIR/venv/bin/pip" install --upgrade pip --quiet
"$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt" --quiet
echo "✓ Dependencies installed"

# 4. Check / install ffmpeg
if ! command -v ffmpeg &>/dev/null; then
  echo "ffmpeg not found. Installing via Homebrew..."
  brew install ffmpeg
fi
echo "✓ ffmpeg is available"

# 5. Create config.json from example if missing
if [ ! -f "$PROJECT_DIR/config.json" ]; then
  cp "$PROJECT_DIR/config.example.json" "$PROJECT_DIR/config.json"
  echo "✓ Created config.json (default download folder: ~/Downloads/VideoGrab)"
else
  echo "✓ config.json already exists"
fi

# 6. Create desktop .app bundle (no Terminal window on launch)
APP_PATH="$HOME/Desktop/WAJA Video Grabber.app"
rm -rf "$APP_PATH"
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/Resources"

cat > "$APP_PATH/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>WAJA Video Grabber</string>
  <key>CFBundleDisplayName</key>
  <string>WAJA Video Grabber</string>
  <key>CFBundleIdentifier</key>
  <string>com.waja.videograbber</string>
  <key>CFBundleVersion</key>
  <string>1.0</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleExecutable</key>
  <string>launcher</string>
  <key>LSUIElement</key>
  <true/>
</dict>
</plist>
PLIST

cat > "$APP_PATH/Contents/MacOS/launcher" << LAUNCHER
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:\$PATH"

PROJECT="$PROJECT_DIR"
LOG="\$PROJECT/logs/launch.log"
PID_FILE="\$PROJECT/logs/server.pid"
mkdir -p "\$PROJECT/logs"

# If server already running, just open browser
if [ -f "\$PID_FILE" ] && kill -0 \$(cat "\$PID_FILE") 2>/dev/null; then
  open "http://127.0.0.1:8000"
  exit 0
fi

# Kill anything on port 8000
lsof -ti:8000 | xargs kill 2>/dev/null
sleep 0.5

cd "\$PROJECT"

# Update code and deps
[ -d .git ] && git pull --quiet 2>/dev/null
source "\$PROJECT/venv/bin/activate"
pip install -r requirements.txt --quiet 2>/dev/null
pip install -U yt-dlp --quiet 2>/dev/null

# Start server
"\$PROJECT/venv/bin/uvicorn" backend.main:app --host 127.0.0.1 --port 8000 >> "\$LOG" 2>&1 &
SERVER_PID=\$!
echo "\$SERVER_PID" > "\$PID_FILE"

# Open browser
sleep 2
open "http://127.0.0.1:8000"

# Keep alive
wait "\$SERVER_PID"
rm -f "\$PID_FILE"
LAUNCHER

chmod +x "$APP_PATH/Contents/MacOS/launcher"
cp "$PROJECT_DIR/frontend/icon.icns" "$APP_PATH/Contents/Resources/AppIcon.icns"
echo "✓ Desktop app created"

echo ""
echo "=== Setup complete! ==="
echo "Double-click 'WAJA Video Grabber' on your Desktop to launch."
