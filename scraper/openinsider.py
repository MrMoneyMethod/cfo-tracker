"""Scrape CFO insider buys from openinsider.com.

Primary source: http://openinsider.com/screener
Falls back to bundled demo data when the site is unreachable (e.g. sandboxed
environments without outbound access to openinsider.com).
"""

from __future__ import annotations

import csv
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("cfo-tracker.scraper")

OPENINSIDER_URL = "http://openinsider.com/screener"

# A CFO typically holds one of these officer titles.
CFO_TITLE_KEYWORDS = (
    "cfo",
    "chief financial officer",
    "chief financial officer ",
    "chief financial",
    "finance",
)

# Default demo data so the app is fully functional offline / when the site is
# unreachable. These are realistic-looking illustrative records only.
DEMO_BUYS = [
    {
        "ticker": "AAPL",
        "name": "Apple Inc",
        "filing_date": "2024-11-01",
        "trade_date": "2024-10-30",
        "insider_name": "Luca Maestri",
        "insider_title": "Chief Financial Officer",
        "trade_type": "P - Purchase",
        "price": 178.50,
        "shares": 10_000,
        "value": 1_785_000,
        "source": "demo",
    },
    {
        "ticker": "MSFT",
        "name": "Microsoft Corp",
        "filing_date": "2024-10-28",
        "trade_date": "2024-10-25",
        "insider_name": "Amy Hood",
        "insider_title": "Chief Financial Officer",
        "trade_type": "P - Purchase",
        "price": 420.10,
        "shares": 5_000,
        "value": 2_100_500,
        "source": "demo",
    },
    {
        "ticker": "GOOGL",
        "name": "Alphabet Inc",
        "filing_date": "2024-10-24",
        "trade_date": "2024-10-22",
        "insider_name": "Ruth Porat",
        "insider_title": "Chief Financial Officer",
        "trade_type": "P - Purchase",
        "price": 162.40,
        "shares": 8_000,
        "value": 1_299_200,
        "source": "demo",
    },
    {
        "ticker": "AMZN",
        "name": "Amazon.com Inc",
        "filing_date": "2024-10-20",
        "trade_date": "2024-10-18",
        "insider_name": "Brian Olsavsky",
        "insider_title": "Chief Financial Officer",
        "trade_type": "P - Purchase",
        "price": 142.60,
        "shares": 12_000,
        "value": 1_711_200,
        "source": "demo",
    },
    {
        "ticker": "JPM",
        "name": "JPMorgan Chase & Co",
        "filing_date": "2024-10-15",
        "trade_date": "2024-10-14",
        "insider_name": "Jeremy Barnum",
        "insider_title": "Chief Financial Officer",
        "trade_type": "P - Purchase",
        "price": 205.30,
        "shares": 3_000,
        "value": 615_900,
        "source": "demo",
    },
    {
        "ticker": "V",
        "name": "Visa Inc",
        "filing_date": "2024-10-10",
        "trade_date": "2024-10-09",
        "insider_name": "Vasant Prabhu",
        "insider_title": "Chief Financial Officer",
        "trade_type": "P - Purchase",
        "price": 275.00,
        "shares": 2_500,
        "value": 687_500,
        "source": "demo",
    },
    {
        "ticker": "UNH",
        "name": "UnitedHealth Group Inc",
        "filing_date": "2024-10-05",
        "trade_date": "2024-10-04",
        "insider_name": "John F. Rexford",
        "insider_title": "Chief Financial Officer",
        "trade_type": "P - Purchase",
        "price": 570.20,
        "shares": 1_000,
        "value": 570_200,
        "source": "demo",
    },
    {
        "ticker": "HD",
        "name": "Home Depot Inc",
        "filing_date": "2024-10-02",
        "trade_date": "2024-10-01",
        "insider_name": "Richard McPhail",
        "insider_title": "Chief Financial Officer",
        "trade_type": "P - Purchase",
        "price": 355.80,
        "shares": 1_500,
        "value": 533_700,
        "source": "demo",
    },
    {
        "ticker": "JNJ",
        "name": "Johnson & Johnson",
        "filing_date": "2024-09-28",
        "trade_date": "2024-09-27",
        "insider_name": "Joseph J. Wolk",
        "insider_title": "Chief Financial Officer",
        "trade_type": "P - Purchase",
        "price": 160.40,
        "shares": 2_000,
        "value": 320_800,
        "source": "demo",
    },
    {
        "ticker": "PG",
        "name": "Procter & Gamble Co",
        "filing_date": "2024-09-25",
        "trade_date": "2024-09-24",
        "insider_name": "Andre Schulten",
        "insider_title": "Chief Financial Officer",
        "trade_type": "P - Purchase",
        "price": 165.90,
        "shares": 1_200,
        "value": 199_080,
        "source": "demo",
    },
]


def _clean(text: Optional[str]) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _parse_number(text: Optional[str]) -> Optional[float]:
    """Parse a number that may contain $, commas, %, parentheses for negatives."""
    if text is None:
        return None
    text = _clean(text)
    if text == "" or text.upper() in ("-", "N/A", "NA"):
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.replace("$", "").replace(",", "").replace("%", "")
    text = text.replace("(", "").replace(")", "").strip()
    try:
        value = float(text)
    except ValueError:
        # grab the first numeric-looking token
        m = re.search(r"-?\d+(?:\.\d+)?", text)
        if not m:
            return None
        value = float(m.group(1))
    return -value if negative else value


def _is_cfo_buy(row: Dict[str, str]) -> bool:
    title = (row.get("insider_title") or "").lower()
    trade_type = (row.get("trade_type") or "").lower()
    if "purchase" not in trade_type and trade_type not in ("p - purchase", "buy"):
        return False
    return any(kw in title for kw in CFO_TITLE_KEYWORDS)


def scrape_cfo_buys(max_rows: int = 200, use_demo_fallback: bool = True) -> List[Dict]:
    """Scrape CFO purchases from openinsider.com.

    Returns a list of dict records. On network failure returns DEMO_BUYS when
    use_demo_fallback is True, otherwise an empty list.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "close",
    }

    # openinsider screener with useful default filters: officer buys, last 90 days
    params = {
        "fdr": "90",          # filing date range last 90 days
        "td": "0",            # trade type: all
        "fkh": "",            # ...
        "fpl": "",            # ...
        "fd": "",             # filing date
        "fdf": "",            # filing date from
        "fdt": "",            # filing date to
        "tdf": "1",           # trade date from (1 day?)
        "tdt": "",            # trade date to
        "is": "",             # insider name
        "il": "",             # insider title like
        "s": "",              # ticker
        "l": "",              # limit
        "c": "",              # ...
        "o": "",              # ...
    }

    try:
        logger.info("Fetching openinsider.com screener ...")
        resp = requests.get(OPENINSIDER_URL, headers=headers, params=params, timeout=25)
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:
        logger.warning("openinsider.com unreachable (%s); using %s", exc,
                       "demo fallback" if use_demo_fallback else "empty result")
        if use_demo_fallback:
            return list(DEMO_BUYS)
        return []

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # openinsider renders results in a table with class "tinytable"
    table = soup.find("table", class_="tinytable")
    if table is None:
        # fallback: any table
        table = soup.find("table")

    rows: List[Dict] = []
    if table is not None:
        header_row = table.find("tr")
        headers_txt = [ _clean(th.get_text(" ", strip=True)) for th in header_row.find_all(["th", "td"]) ] if header_row else []
        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all("td")
            if not cells:
                continue
            cell_texts = [_clean(c.get_text(" ", strip=True)) for c in cells]
            # Map by position; openinsider columns vary, so be defensive.
            record: Dict[str, str] = {}
            if len(headers_txt) == len(cell_texts):
                record = dict(zip(headers_txt, cell_texts))
            else:
                # best-effort positional mapping
                record = {
                    "filing_date": cell_texts[0] if len(cell_texts) > 0 else "",
                    "trade_date": cell_texts[1] if len(cell_texts) > 1 else "",
                    "ticker": cell_texts[2] if len(cell_texts) > 2 else "",
                    "name": cell_texts[3] if len(cell_texts) > 3 else "",
                    "insider_name": cell_texts[4] if len(cell_texts) > 4 else "",
                    "insider_title": cell_texts[5] if len(cell_texts) > 5 else "",
                    "trade_type": cell_texts[6] if len(cell_texts) > 6 else "",
                    "price": cell_texts[7] if len(cell_texts) > 7 else "",
                    "shares": cell_texts[8] if len(cell_texts) > 8 else "",
                    "value": cell_texts[9] if len(cell_texts) > 9 else "",
                }

            if not _is_cfo_buy(record):
                continue

            price = _parse_number(record.get("price"))
            shares = _parse_number(record.get("shares"))
            value = _parse_number(record.get("value"))

            rows.append({
                "ticker": record.get("ticker", "").upper(),
                "name": record.get("name", ""),
                "filing_date": record.get("filing_date", ""),
                "trade_date": record.get("trade_date", ""),
                "insider_name": record.get("insider_name", ""),
                "insider_title": record.get("insider_title", ""),
                "trade_type": record.get("trade_type", ""),
                "price": price,
                "shares": int(shares) if shares is not None else 0,
                "value": value,
                "source": "openinsider",
            })

    if not rows:
        logger.warning("No CFO buy rows parsed from openinsider; using demo fallback")
        if use_demo_fallback:
            return list(DEMO_BUYS)
        return []

    logger.info("Parsed %d CFO buy records from openinsider.com", len(rows))
    return rows[:max_rows]


def load_cfo_buys_csv(path: str) -> List[Dict]:
    """Load CFO buys from a CSV file (alternative data source)."""
    records: List[Dict] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append({
                "ticker": (row.get("ticker") or "").upper(),
                "name": row.get("name") or "",
                "filing_date": row.get("filing_date") or "",
                "trade_date": row.get("trade_date") or "",
                "insider_name": row.get("insider_name") or "",
                "insider_title": row.get("insider_title") or "",
                "trade_type": row.get("trade_type") or "P - Purchase",
                "price": _parse_number(row.get("price")),
                "shares": int(_parse_number(row.get("shares")) or 0),
                "value": _parse_number(row.get("value")),
                "source": "csv",
            })
    return records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    buys = scrape_cfo_buys()
    for b in buys[:5]:
        print(b)
