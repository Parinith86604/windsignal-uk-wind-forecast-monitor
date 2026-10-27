"""Pure data transformation and forecast scoring for the wind forecast monitor.

No network, database, or framework dependencies are used here so the logic is easy to test.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from math import sqrt
from typing import Any, Iterable


def parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO-8601 datetime and normalise it to UTC."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def to_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def extract_rows(payload: Any) -> list[dict[str, Any]]:
    """Handle both stream array responses and object responses containing data."""
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
    return []


def build_analysis(
    actual_payload: Any,
    forecast_payload: Any,
    month: str = "2026-01",
    horizon_hours: int = 24,
) -> dict[str, Any]:
    """Join hourly-aggregated actuals to the latest forecast published at least horizon_hours ahead.

    Elexon FUELHH actual generation is published at 30-minute settlement period resolution,
    whereas WINDFOR forecasts are published on an hourly target cadence (:00).
    To evaluate forecasts fairly without fabricating or interpolating 30-minute forecast values,
    this function aggregates the two half-hourly actual records belonging to each hour into an
    arithmetic mean generation (MW) and matches it to the corresponding hourly WINDFOR forecast.
    """
    if horizon_hours < 1 or horizon_hours > 168:
        raise ValueError("horizon_hours must be between 1 and 168")
    try:
        year_s, month_s = month.split("-", 1)
        year, month_num = int(year_s), int(month_s)
        month_start = datetime(year, month_num, 1, tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        raise ValueError("month must use YYYY-MM format")
    if month_num < 1 or month_num > 12:
        raise ValueError("month must use YYYY-MM format")
    month_end = datetime(year + (month_num == 12), (month_num % 12) + 1, 1, tzinfo=timezone.utc)

    actual_rows = extract_rows(actual_payload)
    forecast_rows = extract_rows(forecast_payload)

    # 1. Collect valid half-hourly actuals, deduplicating by publishTime if needed
    half_hourly_actuals: dict[datetime, dict[str, Any]] = {}
    for row in actual_rows:
        fuel = str(row.get("fuelType", "")).upper()
        if fuel != "WIND":
            continue
        start = parse_datetime(row.get("startTime"))
        generation = to_number(row.get("generation"))
        if start is None or generation is None or not (month_start <= start < month_end):
            continue
        existing = half_hourly_actuals.get(start)
        publish_time = parse_datetime(row.get("publishTime"))
        existing_publish_dt = existing.get("_publish_dt") if existing else None
        should_replace = (
            existing is None
            or (publish_time is not None and (existing_publish_dt is None or publish_time >= existing_publish_dt))
        )
        if should_replace:
            half_hourly_actuals[start] = {
                "time": start,
                "actual_mw": generation,
                "settlement_period": row.get("settlementPeriod"),
                "_publish_dt": publish_time,
            }

    # 2. Group half-hourly actuals by hour.
    # An hour is complete ONLY if both expected half-hour actual records (:00 and :30) are present.
    actuals_by_hour: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
    for dt, rec in half_hourly_actuals.items():
        hour_start = dt.replace(minute=0, second=0, microsecond=0)
        actuals_by_hour[hour_start].append(rec)

    complete_hourly_actuals: dict[datetime, dict[str, Any]] = {}
    incomplete_actual_hours: list[dict[str, Any]] = []

    for hour_start, half_hour_records in actuals_by_hour.items():
        if len(half_hour_records) == 2:
            # Complete hour: arithmetic mean of the two 30-minute settlement periods
            mean_mw = sum(r["actual_mw"] for r in half_hour_records) / 2.0
            periods = sorted(
                [int(r["settlement_period"]) for r in half_hour_records if r.get("settlement_period") is not None]
            )
            complete_hourly_actuals[hour_start] = {
                "time": hour_start,
                "actual_mw": mean_mw,
                "half_hour_count": 2,
                "settlement_periods": periods,
            }
        elif len(half_hour_records) == 1:
            # Incomplete hour: exactly 1 half-hour record present.
            # Excluded from primary accuracy scoring to avoid misleading metrics.
            incomplete_actual_hours.append({
                "time": hour_start.isoformat().replace("+00:00", "Z"),
                "half_hour_count": 1,
                "present_settlement_periods": [
                    int(r["settlement_period"]) for r in half_hour_records if r.get("settlement_period") is not None
                ],
            })

    # 3. Collect valid WINDFOR hourly forecasts
    forecasts_by_target: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
    for row in forecast_rows:
        start = parse_datetime(row.get("startTime"))
        publish = parse_datetime(row.get("publishTime"))
        generation = to_number(row.get("generation"))
        if start is None or publish is None or generation is None:
            continue
        if not (month_start <= start < month_end):
            continue
        # WINDFOR targets are hourly (:00)
        if start.minute == 0:
            forecasts_by_target[start].append({"publish_dt": publish, "generation": generation})

    # 4. Match complete hourly actuals with latest eligible forecast before cutoff
    intervals: list[dict[str, Any]] = []
    no_forecast = 0
    for start in sorted(complete_hourly_actuals):
        cutoff = start - timedelta(hours=horizon_hours)
        available = [row for row in forecasts_by_target.get(start, []) if row["publish_dt"] <= cutoff]
        if not available:
            no_forecast += 1
            continue
        selected = max(available, key=lambda row: row["publish_dt"])
        actual = complete_hourly_actuals[start]["actual_mw"]
        forecast = selected["generation"]
        error = forecast - actual
        lead_hours = (start - selected["publish_dt"]).total_seconds() / 3600
        intervals.append({
            "time": start.isoformat().replace("+00:00", "Z"),
            "date": start.date().isoformat(),
            "settlement_periods": complete_hourly_actuals[start]["settlement_periods"],
            "half_hour_count": complete_hourly_actuals[start]["half_hour_count"],
            "actual_mw": round(actual, 3),
            "forecast_mw": round(forecast, 3),
            "error_mw": round(error, 3),
            "absolute_error_mw": round(abs(error), 3),
            "publish_time": selected["publish_dt"].isoformat().replace("+00:00", "Z"),
            "lead_hours": round(lead_hours, 2),
        })

    expected_hours = int((month_end - month_start).total_seconds() / 3600)
    complete_count = len(complete_hourly_actuals)
    incomplete_count = len(incomplete_actual_hours)
    missing_actual_hours = max(0, expected_hours - (complete_count + incomplete_count))
    matched = len(intervals)
    errors = [row["error_mw"] for row in intervals]
    absolute_errors = [abs(value) for value in errors]
    actual_values = [row["actual_mw"] for row in intervals]
    forecast_values = [row["forecast_mw"] for row in intervals]

    mae = sum(absolute_errors) / matched if matched else None
    rmse = sqrt(sum(value * value for value in errors) / matched) if matched else None
    bias = sum(errors) / matched if matched else None
    total_actual = sum(actual_values)
    wape = (sum(absolute_errors) / total_actual * 100) if matched and total_actual > 0 else None

    # Energy calculations: each interval represents 1.0 hour in hourly evaluation
    forecast_error_mwh = sum(errors) * 1.0 if matched else 0.0
    absolute_error_mwh = sum(absolute_errors) * 1.0 if matched else 0.0

    daily_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in intervals:
        daily_buckets[row["date"]].append(row)
    daily: list[dict[str, Any]] = []
    for day in sorted(daily_buckets):
        rows = daily_buckets[day]
        day_errors = [row["error_mw"] for row in rows]
        day_actual = sum(row["actual_mw"] for row in rows) / len(rows)
        day_forecast = sum(row["forecast_mw"] for row in rows) / len(rows)
        day_mae = sum(abs(value) for value in day_errors) / len(rows)
        daily.append({
            "date": day,
            "actual_avg_mw": round(day_actual, 2),
            "forecast_avg_mw": round(day_forecast, 2),
            "mae_mw": round(day_mae, 2),
            "matched_intervals": len(rows),
            "matched_hours": len(rows),
        })

    worst_intervals = sorted(intervals, key=lambda row: row["absolute_error_mw"], reverse=True)[:10]
    return {
        "month": month,
        "timezone": "UTC",
        "horizon_hours": horizon_hours,
        "evaluation_resolution": "hourly",
        "methodology": (
            "Actuals from Elexon FUELHH (WIND) are aggregated to hourly arithmetic means across both "
            "30-minute settlement periods (:00 and :30). Incomplete hours (lacking one half-hour record) "
            "are excluded from accuracy metrics. For each complete target hour, the latest WINDFOR forecast "
            "published at or before (target startTime minus selected lead-time horizon) is selected."
        ),
        "source_urls": {
            "actuals": "https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream",
            "forecasts": "https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream",
        },
        "coverage": {
            "expected_hours": expected_hours,
            "complete_actual_hours": complete_count,
            "incomplete_actual_hours": incomplete_count,
            "missing_actual_hours": missing_actual_hours,
            "matched_hours": matched,
            "hours_without_eligible_forecast": no_forecast,
            "actual_coverage_pct": round(complete_count / expected_hours * 100, 2) if expected_hours else 0,
            "forecast_match_pct_of_actuals": round(matched / complete_count * 100, 2) if complete_count else 0,
            # Backward-compatible aliases for existing bindings
            "actual_hours": complete_count,
            "expected_intervals": expected_hours,
            "actual_intervals": complete_count,
            "matched_intervals": matched,
            "missing_actual_intervals": missing_actual_hours + incomplete_count,
            "actual_intervals_without_eligible_forecast": no_forecast,
        },
        "incomplete_hours": incomplete_actual_hours,
        "metrics": {
            "mae_mw": round(mae, 2) if mae is not None else None,
            "rmse_mw": round(rmse, 2) if rmse is not None else None,
            "bias_mw": round(bias, 2) if bias is not None else None,
            "wape_pct": round(wape, 2) if wape is not None else None,
            "underforecast_intervals": sum(1 for value in errors if value < 0),
            "overforecast_intervals": sum(1 for value in errors if value > 0),
            "forecast_minus_actual_mwh": round(forecast_error_mwh, 2),
            "absolute_error_mwh": round(absolute_error_mwh, 2),
        },
        "daily": daily,
        "intervals": intervals,
        "worst_intervals": worst_intervals,
        "data_notes": [
            "January 2026 is evaluated in UTC across 744 expected hourly intervals.",
            "An hour is considered complete only when both 30-minute settlement period actuals (:00 and :30) are present.",
            "Incomplete hours (with only 1 half-hour actual) are excluded from error scoring and surfaced in coverage.",
            "Actual generation (MW) is the arithmetic mean of the two half-hourly FUELHH settlement periods for each complete hour.",
            "Forecasts are sourced from Elexon WINDFOR, which publishes at 1-hour resolution.",
            "Energy metrics (MWh) use 1.0 hour per interval (MW x 1h = MWh).",
            "Missing eligible forecasts are excluded from error scoring and surfaced in coverage metrics.",
            "Dataset scope note: FUELHH captures transmission-metered outturn; WINDFOR represents National Grid ESO's transmission wind forecast model.",
        ],
    }
