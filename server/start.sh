#!/usr/bin/env bash
# Always run from this script's folder
cd "$(dirname "$0")" || exit 1

echo "============================================"
echo "  SanStudio File Server  —  Starting..."
echo "============================================"

python3 -c "import flask, waitress" 2>/dev/null || pip install -r requirements.txt -q
python3 server.py
