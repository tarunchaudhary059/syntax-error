#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "🐍 Shinobi Jutsu - Python Face Detection Microservice"
echo "=========================================================="

export PYTHONIOENCODING=utf-8
export MPLCONFIGDIR="${TMPDIR:-/tmp}/matplotlib_cache"
mkdir -p "$MPLCONFIGDIR"

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed or not in PATH."
    exit 1
fi

# Create a virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating isolated Python virtual environment in .venv..."
    python3 -m venv .venv
fi

# Activate virtualenv
echo "🔌 Activating virtual environment..."
source .venv/bin/activate

# Check if packages are already functional
if ! python -c "import numpy, cv2, websockets" &> /dev/null; then
    echo "🔄 Installing required packages (using --no-compile to prevent compilation errors)..."
    pip install --upgrade pip
    pip install --no-compile -r requirements.txt
else
    echo "✅ Dependencies verified (numpy, opencv, websockets ready)."
fi

# Clean any corrupted characters in mediapipe test files if present
TEST_FILE=$(find .venv -name "text_embedder_test.py" 2>/dev/null | head -n 1)
if [ -n "$TEST_FILE" ] && [ -f "$TEST_FILE" ]; then
    python -c "
path = '$TEST_FILE'
try:
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        data = f.read()
    if '∂ç' in data:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(data.replace('∂ç', ''))
except Exception:
    pass
" 2>/dev/null || true
fi

echo ""
echo "🚀 Starting Python Face Detection Service..."
python face_detector_service.py
