"""
Daily Currency Conversion Service (USD to SGD).
Fetches historical and live daily exchange rates from Yahoo Finance (USDSGD=X),
caches rates in Firestore collection `currency_rates`, and provides reliable rate resolution.
"""

from datetime import datetime, timezone
import math
from typing import Any, Dict, Optional
import httpx

from app.utils.logger import get_logger

logger = get_logger("currency_service")

DEFAULT_USD_TO_SGD_RATE = 1.350
YAHOO_FINANCE_API_URL = "https://query1.finance.yahoo.com/v8/finance/chart/USDSGD=X?interval=1d&range=5d"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"

# Fast in-memory cache: date_str -> rate
_RATE_CACHE: Dict[str, float] = {}


def get_today_iso_date() -> str:
    """Returns today's UTC date in YYYY-MM-DD format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def fetch_live_usd_sgd_rate(timeout_secs: float = 4.0) -> Optional[float]:
    """
    Fetches the latest USD to SGD market rate from Yahoo Finance chart endpoint.
    """
    try:
        headers = {"User-Agent": USER_AGENT}
        with httpx.Client(timeout=timeout_secs, follow_redirects=True) as client:
            resp = client.get(YAHOO_FINANCE_API_URL, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                result = data.get("chart", {}).get("result", [])
                if result:
                    meta = result[0].get("meta", {})
                    market_price = meta.get("regularMarketPrice")
                    if market_price and float(market_price) > 0:
                        return float(market_price)

                    # Check close quotes
                    quotes = result[0].get("indicators", {}).get("quote", [])
                    if quotes:
                        closes = [c for c in quotes[0].get("close", []) if c is not None]
                        if closes:
                            return float(closes[-1])
    except Exception as exc:
        logger.warning(f"Failed to fetch live USD/SGD rate from Yahoo Finance: {exc}")
    return None


def get_daily_exchange_rate(
    target_date: Optional[str] = None,
    db: Optional[Any] = None,
) -> float:
    """
    Resolves the USD to SGD exchange rate for a given date (defaults to today).
    Resolution priority:
      1. In-memory cache for target_date.
      2. Firestore `currency_rates/{target_date}` document.
      3. Live fetch from Yahoo Finance (if target_date is today or None) and persist to DB.
      4. Most recent cached rate from memory / Firestore.
      5. Safe default fallback (1.350).
    """
    date_key = target_date or get_today_iso_date()

    # 1. In-memory cache
    if date_key in _RATE_CACHE:
        return _RATE_CACHE[date_key]

    # 2. Firestore document lookup
    if db is not None:
        try:
            doc = db.collection("currency_rates").document(date_key).get()
            if doc.exists:
                d_data = doc.to_dict()
                rate = float(d_data.get("rate") or 0.0)
                if rate > 0:
                    _RATE_CACHE[date_key] = rate
                    return rate
        except Exception as err:
            logger.debug(f"Firestore currency rate lookup error for {date_key}: {err}")

    # 3. Live fetch if date is today or no date provided
    if not target_date or target_date == get_today_iso_date():
        live_rate = fetch_live_usd_sgd_rate()
        if live_rate and live_rate > 0:
            _RATE_CACHE[date_key] = live_rate
            if db is not None:
                try:
                    now_iso = datetime.now(timezone.utc).isoformat()
                    db.collection("currency_rates").document(date_key).set({
                        "id": date_key,
                        "date": date_key,
                        "from_currency": "USD",
                        "to_currency": "SGD",
                        "rate": round(live_rate, 4),
                        "source": "yahoo_finance",
                        "fetched_at": now_iso,
                    })
                    logger.info(f"Synced USD/SGD rate for {date_key}: {live_rate:.4f}")
                except Exception as err:
                    logger.warning(f"Failed to write currency rate to Firestore: {err}")
            return live_rate

    # 4. Fallback to any recent rate in cache
    if _RATE_CACHE:
        latest_cached = list(_RATE_CACHE.values())[-1]
        return latest_cached

    # 5. Fallback to latest record in DB
    if db is not None:
        try:
            docs = list(
                db.collection("currency_rates")
                .order_by("date", direction="DESCENDING")
                .limit(1)
                .stream()
            )
            if docs:
                r_val = float(docs[0].to_dict().get("rate") or 0.0)
                if r_val > 0:
                    _RATE_CACHE[date_key] = r_val
                    return r_val
        except Exception:
            pass

    return DEFAULT_USD_TO_SGD_RATE


def sync_daily_exchange_rate(db: Optional[Any] = None) -> Dict[str, Any]:
    """
    Syncs today's USD to SGD rate into Firestore and updates memory cache.
    """
    today_date = get_today_iso_date()
    rate = fetch_live_usd_sgd_rate() or get_daily_exchange_rate(today_date, db=db)
    now_iso = datetime.now(timezone.utc).isoformat()

    record = {
        "id": today_date,
        "date": today_date,
        "from_currency": "USD",
        "to_currency": "SGD",
        "rate": round(rate, 4),
        "source": "yahoo_finance",
        "fetched_at": now_iso,
    }
    _RATE_CACHE[today_date] = record["rate"]

    if db is not None:
        try:
            db.collection("currency_rates").document(today_date).set(record)
            logger.info(f"Successfully synced daily exchange rate: 1 USD = {record['rate']} SGD ({today_date})")
        except Exception as err:
            logger.warning(f"Could not persist daily exchange rate: {err}")

    return record
