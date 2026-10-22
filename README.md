# CFO Insider Buy Tracker

A desktop-style web application that tracks **CFO (Chief Financial Officer) insider purchases**, pulls company fundamentals (market cap, cash, debt, enterprise value), backtests CFO buys against the S&P 500 (SPY), and auto-refreshes every minute.

## How it works

1. **Data source** — Scrapes CFO insider filings from [openinsider.com](http://openinsider.com/) and filters for CFO purchases.
2. **Fundamentals** — For each company, retrieves market cap, total cash, total debt, and enterprise value (via Yahoo Finance / yfinance).
3. **Backtest** — Simulates buying on each CFO trade date and holding for 1 and 3 months, then compares returns to a buy-and-hold in SPY (S&P 500).
4. **Web UI** — Flask dashboard, auto-refreshing every 60 seconds. Open `http://localhost:8080`.
5. **Executable** — Bundled with PyInstaller into a single windowed `.exe` (no console window). Double-click to run.

## Data sources (and offline / demo mode)

- **Primary:** openinsider.com screener (CFO purchases).
- **Fundamentals:** Yahoo Finance via `yfinance`.
- **Fallback:** If either source is unreachable (e.g. a sandboxed or offline machine), the app falls back to bundled illustrative demo data so the UI is still fully functional. You can also import your own CFO-buy CSV via the UI.

## Run from source

Quick launcher scripts (they create the venv, install deps, and start the server):

- `run.sh` — Linux / macOS
- `run.bat` — Windows

Then open `http://localhost:8080` in your browser.

Manually:
```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# or
source .venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
python app.py
# then open http://localhost:8080
```

## Build a Windows `.exe`

The PyInstaller spec (`cfo-tracker.spec`) is configured as **one-file, windowed** (`console=False`), so the produced `.exe` shows no console window — just launch it and open `http://localhost:8080`.

**On Windows:**
```cmd
pip install -r requirements.txt
python build_exe.py
```
Output: `dist/cfo-tracker.exe`

**From Linux/macOS:** PyInstaller produces a native executable for the current OS, not a Windows `.exe`. To get a Windows `.exe`, run `build_exe.py` on a Windows machine (or under Wine with a Windows Python). The included `cfo-tracker.spec` works cross-platform.

## Project layout

```
cfo-tracker/
├── app.py                  # Flask web app + API
├── scraper/
│   ├── openinsider.py      # CFO buy scraper (openinsider.com + demo fallback)
│   └── fundamentals.py     # Market cap, cash, debt, EV (yfinance + demo fallback)
├── backtest/
│   └── engine.py           # Backtest CFO buys vs SPY
├── scheduler.py            # Background refresh every 60 seconds
├── static/style.css        # UI styles
├── templates/              # (UI HTML is embedded in app.py for portability)
├── data/                   # Generated JSON data cache (buys, fundamentals, backtest, meta)
├── cfo-tracker.spec        # PyInstaller spec (one-file, windowed)
├── build_exe.py            # Build script
├── requirements.txt
└── README.md
```

## CSV import format

The UI accepts a CSV import with columns:
`ticker,name,filing_date,trade_date,insider_name,insider_title,trade_type,price,shares,value`

Example:
```
ticker,name,trade_date,insider_name,insider_title,trade_type,price,shares,value
AAPL,Apple Inc,2024-10-30,Luca Maestri,Chief Financial Officer,P - Purchase,178.50,10000,1785000
```