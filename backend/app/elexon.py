"""Small client for Elexon's public Insights dataset endpoints."""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

from .analysis import extract_rows

BASE_URL = os.getenv("ELEXON_API_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1")
CACHE_TTL_SECONDS = int(os.getenv("ELEXON_CACHE_TTL_SECONDS", "900"))
_TIMEOUT_SECONDS = 25
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()


class ElexonAPIError(RuntimeError):
    pass


def _request_dataset(dataset: str, params: dict[str, str]) -> Any:
    if requests is None:
        raise ElexonAPIError("The 'requests' package is required to query Elexon. Install backend/requirements.txt.")
    cache_key = dataset + "?" + urlencode(sorted(params.items()))
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]
    url = f"{BASE_URL}/datasets/{dataset}/stream"
    try:
        response = requests.get(url, params=params, timeout=_TIMEOUT_SECONDS, headers={"Accept": "application/json"})
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise ElexonAPIError(f"Elexon {dataset} request failed: {exc}") from exc
    except ValueError as exc:
        raise ElexonAPIError(f"Elexon {dataset} returned invalid JSON") from exc
    if not isinstance(payload, (list, dict)):
        raise ElexonAPIError(f"Elexon {dataset} returned an unexpected response shape")
    with _cache_lock:
        _cache[cache_key] = (now, payload)
    return payload


def build_fuelhh_params(month: str) -> dict[str, str]:
    """Build query parameters for Elexon FUELHH/stream endpoint.

    Uses documented settlement date range parameters in yyyy-MM-dd format.
    The end date is set to the last calendar day of the month so January 31 is included.
    """
    try:
        year_s, month_s = month.split("-", 1)
        year, month_num = int(year_s), int(month_s)
        start = datetime(year, month_num, 1, tzinfo=timezone.utc)
    except (ValueError, AttributeError) as exc:
        raise ValueError("month must use YYYY-MM format") from exc
    if not 1 <= month_num <= 12:
        raise ValueError("month must use YYYY-MM format")
    end = datetime(year + (month_num == 12), (month_num % 12) + 1, 1, tzinfo=timezone.utc)
    last_day = end - timedelta(days=1)
    return {
        "settlementDateFrom": start.strftime("%Y-%m-%d"),
        "settlementDateTo": last_day.strftime("%Y-%m-%d"),
        "fuelType": "WIND",
    }


def build_windfor_params(month: str, max_horizon_hours: int = 168) -> dict[str, str]:
    """Build query parameters for Elexon WINDFOR/stream endpoint.

    Uses documented publishDateTimeFrom and publishDateTimeTo parameters (ISO-8601).
    Fetches forecasts published up to month end, starting far enough back to evaluate
    the maximum configured lead time.
    """
    try:
        year_s, month_s = month.split("-", 1)
        year, month_num = int(year_s), int(month_s)
        start = datetime(year, month_num, 1, tzinfo=timezone.utc)
    except (ValueError, AttributeError) as exc:
        raise ValueError("month must use YYYY-MM format") from exc
    if not 1 <= month_num <= 12:
        raise ValueError("month must use YYYY-MM format")
    end = datetime(year + (month_num == 12), (month_num % 12) + 1, 1, tzinfo=timezone.utc)
    fmt = lambda dt: dt.isoformat(timespec="seconds").replace("+00:00", "Z")
    publication_start = start - timedelta(hours=max_horizon_hours + 24)
    return {
        "publishDateTimeFrom": fmt(publication_start),
        "publishDateTimeTo": fmt(end),
    }


def get_month_payloads(month: str, max_horizon_hours: int = 168) -> tuple[Any, Any]:
    """Fetch January 2026 actuals and a publication window wide enough for selected lead times."""
    actual_params = build_fuelhh_params(month)
    forecast_params = build_windfor_params(month, max_horizon_hours=max_horizon_hours)
    actual_payload = _request_dataset("FUELHH", actual_params)
    forecast_payload = _request_dataset("WINDFOR", forecast_params)
    if not extract_rows(actual_payload):
        raise ElexonAPIError("Elexon FUELHH returned no actual-generation rows for the requested month.")
    if not extract_rows(forecast_payload):
        raise ElexonAPIError(
            "Elexon WINDFOR returned no forecast rows for the requested month/publication window. "
            "Check the endpoint schema and query parameters before presenting results."
        )
    return actual_payload, forecast_payload
