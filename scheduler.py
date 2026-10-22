"""Background scheduler: refresh CFO buys, fundamentals, and backtest every minute."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Dict, List

from apscheduler.schedulers.background import BackgroundScheduler

import paths
from scraper.openinsider import scrape_cfo_buys
from scraper.fundamentals import get_fundamentals, format_value
from backtest.engine import backtest

logger = logging.getLogger("cfo-tracker.scheduler")

DATA_DIR = paths.data_dir()
BUYS_PATH = paths.BUYS_PATH
FUND_PATH = paths.FUND_PATH
BACKTEST_PATH = paths.BACKTEST_PATH
META_PATH = paths.META_PATH

DEMO_NOTE = (
    "Live data from openinsider.com / Yahoo Finance was unreachable from this "
    "environment, so illustrative demo data is shown. Replace with real data by "
    "running on a machine with outbound internet, or import your own CSV via the UI."
)


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def refresh_all(use_demo_fallback: bool = True) -> Dict:
    """Run a full refresh: scrape buys, load fundamentals, backtest."""
    logger.info("=== Refresh cycle started at %s ===", _now_iso())

    # 1. CFO buys
    try:
        buys = scrape_cfo_buys(use_demo_fallback=use_demo_fallback)
    except Exception as exc:
        logger.exception("scrape_cfo_buys failed: %s", exc)
        from scraper.openinsider import DEMO_BUYS
        buys = list(DEMO_BUYS)

    # Attach formatted price/value for display
    for b in buys:
        b["price_fmt"] = f"${b['price']:,.2f}" if b.get("price") is not None else "N/A"
        b["value_fmt"] = f"${b['value']:,.2f}" if b.get("value") is not None else "N/A"

    _save_json(BUYS_PATH, buys)

    # 2. Fundamentals for all unique tickers
    tickers = sorted({b["ticker"] for b in buys if b.get("ticker")})
    try:
        fundamentals = get_fundamentals(tickers)
    except Exception as exc:
        logger.exception("get_fundamentals failed: %s", exc)
        fundamentals = {}

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

    # 3. Backtest vs SPY
    try:
        bt = backtest(buys, horizons_months=(1, 3))
    except Exception as exc:
        logger.exception("backtest failed: %s", exc)
        bt = {"trades": [], "aggregate": {}, "note": f"Backtest error: {exc}"}

    _save_json(BACKTEST_PATH, bt)

    # 4. Meta
    source = buys[0].get("source", "demo") if buys else "demo"
    is_demo = source == "demo" or all(b.get("source") == "demo" for b in buys)
    meta = {
        "last_update": _now_iso(),
        "update_interval_seconds": 60,
        "n_buys": len(buys),
        "source": source,
        "demo": is_demo,
        "note": DEMO_NOTE if is_demo else "Live data from openinsider.com and Yahoo Finance.",
    }
    _save_json(META_PATH, meta)

    logger.info("=== Refresh complete: %d buys, source=%s ===", len(buys), source)
    return {"buys": buys, "fundamentals": fund_out, "backtest": bt, "meta": meta}


def start_scheduler(use_demo_fallback: bool = True) -> BackgroundScheduler:
    """Start the background scheduler (refresh every 60 seconds)."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        refresh_all,
        "interval",
        seconds=60,
        args=[use_demo_fallback],
        id="cfo_refresh",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    # run once immediately
    refresh_all(use_demo_fallback=use_demo_fallback)
    return scheduler


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = refresh_all()
    print("Meta:", result["meta"])
