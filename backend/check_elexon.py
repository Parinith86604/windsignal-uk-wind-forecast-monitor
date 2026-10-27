"""Run from the repository root: python -m backend.check_elexon"""
from __future__ import annotations

import json

from backend.app.analysis import build_analysis, extract_rows
from backend.app.elexon import get_month_payloads


def main() -> None:
    actual_payload, forecast_payload = get_month_payloads("2026-01", max_horizon_hours=168)
    actual_rows = extract_rows(actual_payload)
    forecast_rows = extract_rows(forecast_payload)
    print("FUELHH response type:", type(actual_payload).__name__)
    print("FUELHH rows:", len(actual_rows))
    print("FUELHH sample keys:", sorted(actual_rows[0].keys()) if actual_rows else [])
    print("FUELHH sample row:", json.dumps(actual_rows[0], indent=2) if actual_rows else "<empty>")
    print("WINDFOR response type:", type(forecast_payload).__name__)
    print("WINDFOR rows:", len(forecast_rows))
    print("WINDFOR sample keys:", sorted(forecast_rows[0].keys()) if forecast_rows else [])
    print("WINDFOR sample row:", json.dumps(forecast_rows[0], indent=2) if forecast_rows else "<empty>")
    fuel_types = sorted({str(row.get("fuelType", "<missing>")) for row in actual_rows})
    print("FUELHH fuel types present:", fuel_types)
    publish_times = sorted({str(row.get("publishTime")) for row in forecast_rows if row.get("publishTime")})
    print("Distinct forecast publishTime values:", len(publish_times))
    print("Earliest forecast publishTime:", publish_times[0] if publish_times else "<missing>")
    print("Latest forecast publishTime:", publish_times[-1] if publish_times else "<missing>")
    result = build_analysis(actual_payload, forecast_payload, month="2026-01", horizon_hours=24)
    print("24h coverage:", json.dumps(result["coverage"], indent=2))
    print("24h metrics:", json.dumps(result["metrics"], indent=2))
    if not result["coverage"]["matched_intervals"]:
        raise SystemExit("No actual/forecast pairs matched; do not submit until the source query/schema is fixed.")


if __name__ == "__main__":
    main()
