#!/bin/bash
# ==============================================================================
# Double-clickable macOS Launcher for Apple HEIC Converter Studio
# ==============================================================================

cd "$(dirname "$0")"

if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is required to run HEICto-."
    read -p "Press Enter to exit..."
    exit 1
fi

PORT=5173

# Open default browser after 1 second
(sleep 1.2 && open "http://localhost:${PORT}" 2>/dev/null || true) &

echo "🚀 Starting HEICto-..."
exec python3 app.py "$PORT"

