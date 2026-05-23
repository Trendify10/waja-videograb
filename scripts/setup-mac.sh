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

# 6. Create desktop launcher
LAUNCHER_PATH="$HOME/Desktop/WAJA Video Grabber.command"
cat > "$LAUNCHER_PATH" << LAUNCHER
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:\$PATH"
cd "$PROJECT_DIR"
bash scripts/launch-mac.command
LAUNCHER
chmod +x "$LAUNCHER_PATH"
echo "✓ Desktop launcher created"

echo ""
echo "=== Setup complete! ==="
echo "Double-click 'WAJA Video Grabber' on your Desktop to launch."
