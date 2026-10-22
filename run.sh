#!/usr/bin/env bash
# Run the CFO Insider Buy Tracker from source (Linux / macOS).
# Then open http://localhost:8080 in your browser.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

.venv/bin/pip install -q -r requirements.txt

echo "Starting CFO tracker on http://localhost:8080 ..."
.venv/bin/python app.py
