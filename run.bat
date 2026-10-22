@echo off
REM Run the CFO Insider Buy Tracker from source (Windows).
REM Then open http://localhost:8080 in your browser.
setlocal enabledelayedexpansion

cd /d "%~dp0"

if not exist ".venv" (
  echo Creating virtual environment...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
pip install -q -r requirements.txt

echo Starting CFO tracker on http://localhost:8080 ...
python app.py
