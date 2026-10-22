"""CFO Insider Buy Tracker — Flask web application.

Endpoints:
  GET  /              -> main dashboard UI
  GET  /api/buys      -> CFO buy records
  GET  /api/fundamentals -> company fundamentals
  GET  /api/backtest  -> backtest results vs SPY
  GET  /api/meta      -> last-update metadata
  POST /api/import    -> upload a CSV of CFO buys (alternative data source)
  GET  /api/refresh   -> force an immediate data refresh

Runs a background scheduler that refreshes data every 60 seconds.
"""

from __future__ import annotations

import logging
import os
import tempfile
from threading import Lock

from flask import Flask, render_template_string, request, jsonify, send_from_directory

import paths
from scheduler import refresh_all, start_scheduler, BUYS_PATH, FUND_PATH, BACKTEST_PATH, META_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cfo-tracker.app")

app = Flask(
    __name__,
    static_folder=paths.static_dir(),
    template_folder=paths.templates_dir(),
    static_url_path="/static",
)

_refresh_lock = Lock()
_scheduler = None


def _read_json(path, default):
    import json
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Start the background refresh scheduler once (safe for reloader)
# ---------------------------------------------------------------------------
_scheduler_started = False


def ensure_scheduler():
    global _scheduler, _scheduler_started
    if not _scheduler_started:
        _scheduler = start_scheduler(use_demo_fallback=True)
        _scheduler_started = True


# Run initial refresh before first request (works under PyInstaller onefile too)
with app.app_context():
    try:
        refresh_all(use_demo_fallback=True)
    except Exception as exc:
        logger.exception("Initial refresh failed: %s", exc)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template_string(INDEX_HTML)


@app.route("/api/meta")
def api_meta():
    return jsonify(_read_json(META_PATH, {}))


@app.route("/api/buys")
def api_buys():
    return jsonify(_read_json(BUYS_PATH, []))


@app.route("/api/fundamentals")
def api_fundamentals():
    return jsonify(_read_json(FUND_PATH, {}))


@app.route("/api/backtest")
def api_backtest():
    return jsonify(_read_json(BACKTEST_PATH, {}))


@app.route("/api/refresh", methods=["POST", "GET"])
def api_refresh():
    with _refresh_lock:
        try:
            result = refresh_all(use_demo_fallback=True)
            return jsonify({
                "status": "ok",
                "n_buys": len(result.get("buys", [])),
                "meta": result.get("meta", {}),
            })
        except Exception as exc:
            logger.exception("Manual refresh failed: %s", exc)
            return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/import", methods=["POST"])
def api_import():
    """Import CFO buys from an uploaded CSV and refresh."""
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "No file selected"}), 400

    from scraper.openinsider import load_cfo_buys_csv

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    try:
        file.save(tmp.name)
        buys = load_cfo_buys_csv(tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

    if not buys:
        return jsonify({"status": "error", "message": "No valid CFO buy records in CSV"}), 400

    import json as _json
    for b in buys:
        b["price_fmt"] = f"${b['price']:,.2f}" if b.get("price") is not None else "N/A"
        b["value_fmt"] = f"${b['value']:,.2f}" if b.get("value") is not None else "N/A"
    _save_json(BUYS_PATH, buys)

    # Refresh fundamentals + backtest for the imported tickers
    from scheduler import _save_json, FUND_PATH, BACKTEST_PATH, META_PATH, _now_iso
    from scraper.fundamentals import get_fundamentals, format_value
    from backtest.engine import backtest

    tickers = sorted({b["ticker"] for b in buys if b.get("ticker")})
    fundamentals = get_fundamentals(tickers)
    fund_out = {}
    for t, d in fundamentals.items():
        fund_out[t] = {
            "market_cap": d.get("market_cap"),
            "cash": d.get("cash"),
            "debt": d.get("debt"),
            "enterprise_value": d.get("enterprise_value"),
            "market_cap_fmt": format_value(d.get("market_cap")),
            "cash_fmt": format_value(d.get("cash")),
            "debt_fmt": format_value(d.get("debt")),
            "enterprise_value_fmt": format_value(d.get("enterprise_value")),
        }
    _save_json(FUND_PATH, fund_out)

    bt = backtest(buys, horizons_months=(1, 3))
    _save_json(BACKTEST_PATH, bt)

    meta = {
        "last_update": _now_iso(),
        "update_interval_seconds": 60,
        "n_buys": len(buys),
        "source": "csv",
        "demo": False,
        "note": "Imported from uploaded CSV.",
    }
    _save_json(META_PATH, meta)

    return jsonify({"status": "ok", "n_buys": len(buys), "meta": meta})


def _save_json(path, data):
    import json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(data, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# HTML UI (single file for portability under PyInstaller)
# ---------------------------------------------------------------------------
INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CFO Insider Buy Tracker</title>
<link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
<div class="container">
  <header>
    <h1>📈 CFO Insider Buy Tracker</h1>
    <div class="meta" id="meta">Loading&hellip;</div>
  </header>

  <div class="toolbar">
    <button onclick="loadData()">⟳ Refresh Now</button>
    <button onclick="document.getElementById('csvInput').click()">📁 Import CSV</button>
    <input type="file" id="csvInput" accept=".csv" style="display:none" onchange="importCsv(this)">
    <span class="badge" id="srcBadge">—</span>
    <span class="status" id="autoStatus">Updating every 60s&hellip;</span>
  </div>

  <!-- CFO Buys Table -->
  <section class="card">
    <h2>CFO Purchases <span class="count" id="buysCount">0</span></h2>
    <div class="table-wrap">
      <table id="buysTable">
        <thead>
          <tr>
            <th>Ticker</th><th>Company</th><th>CFO / Insider</th><th>Title</th>
            <th>Trade Date</th><th>Price</th><th>Shares</th><th>Value</th><th>Source</th>
          </tr>
        </thead>
        <tbody id="buysTbody"></tbody>
      </table>
    </div>
  </section>

  <!-- Fundamentals -->
  <section class="card">
    <h2>Company Fundamentals</h2>
    <div class="table-wrap">
      <table id="fundTable">
        <thead>
          <tr>
            <th>Ticker</th><th>Market Cap</th><th>Cash</th><th>Total Debt</th><th>Enterprise Value</th>
          </tr>
        </thead>
        <tbody id="fundTbody"></tbody>
      </table>
    </div>
  </section>

  <!-- Backtest vs S&P 500 -->
  <section class="card">
    <h2>Backtest: CFO Buys vs S&amp;P 500 (SPY)</h2>
    <div class="stats-grid" id="btStats"></div>
    <div class="chart-wrap">
      <canvas id="btChart"></canvas>
    </div>
    <p class="note" id="btNote"></p>
  </section>

  <footer>
    Data source: <a href="http://openinsider.com/" target="_blank" rel="noopener">openinsider.com</a> ·
    Fundamentals via Yahoo Finance · Backtest vs SPY · Auto-updates every 60 seconds
  </footer>
</div>

<script>
let btChart = null;

async function loadData() {
  const [metaRes, buysRes, fundRes, btRes] = await Promise.all([
    fetch('/api/meta'), fetch('/api/buys'), fetch('/api/fundamentals'), fetch('/api/backtest')
  ]);
  const meta = await metaRes.json();
  const buys = await buysRes.json();
  const funds = await fundRes.json();
  const bt = await btRes.json();

  renderMeta(meta);
  renderBuys(buys);
  renderFundamentals(funds);
  renderBacktest(bt);
}

function renderMeta(meta) {
  const el = document.getElementById('meta');
  const badge = document.getElementById('srcBadge');
  const note = meta.demo ? '(demo data — live sources unreachable)' : '(live data)';
  el.textContent = `Last update: ${meta.last_update || '—'}  ${note}  ·  ${meta.n_buys || 0} CFO buys`;
  badge.textContent = (meta.source || 'unknown').toUpperCase();
  badge.className = 'badge ' + (meta.demo ? 'demo' : 'live');
  document.getElementById('autoStatus').textContent = meta.demo
    ? 'Demo mode: refreshing every 60s from bundled data.'
    : 'Auto-refreshing every 60s.';
}

function renderBuys(buys) {
  const tbody = document.getElementById('buysTbody');
  tbody.innerHTML = '';
  document.getElementById('buysCount').textContent = buys.length;
  for (const b of buys) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${escapeHtml(b.ticker)}</strong></td>
      <td>${escapeHtml(b.name)}</td>
      <td>${escapeHtml(b.insider_name)}</td>
      <td>${escapeHtml(b.insider_title)}</td>
      <td>${escapeHtml(b.trade_date)}</td>
      <td>${escapeHtml(b.price_fmt)}</td>
      <td>${b.shares != null ? b.shares.toLocaleString() : '—'}</td>
      <td>${escapeHtml(b.value_fmt)}</td>
      <td><span class="src">${escapeHtml(b.source)}</span></td>
    `;
    tbody.appendChild(tr);
  }
}

function renderFundamentals(funds) {
  const tbody = document.getElementById('fundTbody');
  tbody.innerHTML = '';
  for (const [ticker, d] of Object.entries(funds).sort()) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${escapeHtml(ticker)}</strong></td>
      <td>${escapeHtml(d.market_cap_fmt)}</td>
      <td>${escapeHtml(d.cash_fmt)}</td>
      <td>${escapeHtml(d.debt_fmt)}</td>
      <td>${escapeHtml(d.enterprise_value_fmt)}</td>
    `;
    tbody.appendChild(tr);
  }
}

function renderBacktest(bt) {
  const agg = bt.aggregate || {};
  const grid = document.getElementById('btStats');
  grid.innerHTML = '';

  const overall = agg.overall || {};
  grid.innerHTML = `
    <div class="stat"><div class="stat-val">${overall.n_trades || 0}</div><div class="stat-label">Total Trades</div></div>
    <div class="stat"><div class="stat-val">${(overall.avg_stock_return * 100).toFixed(2)}%</div><div class="stat-label">Avg Stock Return</div></div>
    <div class="stat"><div class="stat-val">${(overall.avg_alpha * 100).toFixed(2)}%</div><div class="stat-label">Avg Alpha vs SPY</div></div>
    <div class="stat"><div class="stat-val">${(overall.win_rate * 100).toFixed(1)}%</div><div class="stat-label">Win Rate</div></div>
  `;

  // per-horizon bars
  const labels = [], stock = [], spy = [], alpha = [];
  for (const [k, v] of Object.entries(agg)) {
    if (k === 'overall') continue;
    labels.push(k);
    stock.push((v.avg_stock_return || 0) * 100);
    spy.push((v.avg_spy_return || 0) * 100);
    alpha.push((v.avg_alpha || 0) * 100);
  }

  const ctx = document.getElementById('btChart').getContext('2d');
  if (btChart) btChart.destroy();
  btChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        { label: 'Avg Stock Return', data: stock, backgroundColor: '#2563eb' },
        { label: 'Avg SPY Return', data: spy, backgroundColor: '#94a3b8' },
        { label: 'Avg Alpha', data: alpha, backgroundColor: '#10b981' },
      ]
    },
    options: {
      responsive: true,
      plugins: { title: { display: true, text: 'Average Return by Holding Period (CFO Buys vs SPY)' } },
      scales: { y: { beginAtZero: false, ticks: { callback: v => v + '%' } } }
    }
  });

  document.getElementById('btNote').textContent = bt.note || '';
}

async function importCsv(input) {
  if (!input.files.length) return;
  const form = new FormData();
  form.append('file', input.files[0]);
  try {
    const r = await fetch('/api/import', { method: 'POST', body: form });
    const j = await r.json();
    if (j.status === 'ok') {
      alert('Imported ' + j.n_buys + ' CFO buys from CSV.');
      loadData();
    } else {
      alert('Import failed: ' + (j.message || 'unknown error'));
    }
  } catch (e) {
    alert('Import error: ' + e);
  }
  input.value = '';
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// Initial load + auto refresh every 60s
loadData();
setInterval(loadData, 60000);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    ensure_scheduler()
    app.run(host="0.0.0.0", port=8080, debug=False)
