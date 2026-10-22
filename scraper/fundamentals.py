"""Company fundamentals (market cap, cash, debt, enterprise value).

Primary source: yfinance (Yahoo Finance). Falls back to demo data when Yahoo is
unreachable so the app remains fully functional offline.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

import yfinance as yf

logger = logging.getLogger("cfo-tracker.fundamentals")

# Demo fundamentals mirroring the demo CFO buys tickers. Illustrative only.
DEMO_FUNDAMENTALS = {
    "AAPL": {"market_cap": 3_450_000_000_000, "cash": 65_000_000_000, "debt": 108_000_000_000, "enterprise_value": 3_493_000_000_000},
    "MSFT": {"market_cap": 3_300_000_000_000, "cash": 78_000_000_000, "debt": 48_000_000_000, "enterprise_value": 3_270_000_000_000},
    "GOOGL": {"market_cap": 2_100_000_000_000, "cash": 115_000_000_000, "debt": 14_000_000_000, "enterprise_value": 1_999_000_000_000},
    "AMZN": {"market_cap": 1_950_000_000_000, "cash": 86_000_000_000, "debt": 55_000_000_000, "enterprise_value": 1_919_000_000_000},
    "JPM": {"market_cap": 560_000_000_000, "cash": 20_000_000_000, "debt": 280_000_000_000, "enterprise_value": 820_000_000_000},
    "V": {"market_cap": 540_000_000_000, "cash": 12_000_000_000, "debt": 22_000_000_000, "enterprise_value": 550_000_000_000},
    "UNH": {"market_cap": 460_000_000_000, "cash": 14_000_000_000, "debt": 45_000_000_000, "enterprise_value": 491_000_000_000},
    "HD": {"market_cap": 390_000_000_000, "cash": 5_000_000_000, "debt": 48_000_000_000, "enterprise_value": 433_000_000_000},
    "JNJ": {"market_cap": 430_000_000_000, "cash": 15_000_000_000, "debt": 32_000_000_000, "enterprise_value": 447_000_000_000},
    "PG": {"market_cap": 395_000_000_000, "cash": 7_000_000_000, "debt": 26_000_000_000, "enterprise_value": 414_000_000_000},
}


def get_fundamentals(tickers) -> Dict[str, Dict]:
    """Return fundamentals for a list of tickers.

    Keys: market_cap, cash, debt, enterprise_value (all floats or None).
    Falls back to demo data per ticker when yfinance fails.
    """
    if isinstance(tickers, str):
        tickers = [tickers]
    tickers = [t.upper() for t in tickers if t]
    result: Dict[str, Dict] = {}

    for ticker in tickers:
        data = {"market_cap": None, "cash": None, "debt": None, "enterprise_value": None}
        try:
            tk = yf.Ticker(ticker)
            info = tk.info or {}
            data["market_cap"] = info.get("marketCap")
            data["cash"] = info.get("totalCash")
            data["debt"] = info.get("totalDebt")
            data["enterprise_value"] = info.get("enterpriseValue")
        except Exception as exc:
            logger.warning("yfinance failed for %s (%s); using demo", ticker, exc)

        # fill missing from demo
        if any(v is None for v in data.values()):
            demo = DEMO_FUNDAMENTALS.get(ticker)
            if demo:
                for k in data:
                    if data[k] is None:
                        data[k] = demo[k]

        result[ticker] = data

    return result


def format_value(value) -> str:
    if value is None:
        return "N/A"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(v) >= 1e12:
        return f"${v/1e12:,.2f}T"
    if abs(v) >= 1e9:
        return f"${v/1e9:,.2f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:,.2f}M"
    return f"${v:,.2f}"


if __name__ == "__main__":
    import json
    print(json.dumps(get_fundamentals(["AAPL", "MSFT"]), indent=2, default=str))
