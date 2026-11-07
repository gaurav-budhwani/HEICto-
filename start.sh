#!/usr/bin/env bash
# ==============================================================================
# Apple HEIC & Image Format Converter Launcher
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed or not in PATH."
    exit 1
fi

PORT=5173

# Open default browser after 1 second in background
(sleep 1.2 && open "http://localhost:${PORT}" 2>/dev/null || true) &

# Run server
exec python3 app.py "$PORT"

