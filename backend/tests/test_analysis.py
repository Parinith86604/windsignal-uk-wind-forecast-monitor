import unittest
from datetime import datetime, timezone

from backend.app.analysis import build_analysis, extract_rows, parse_datetime
from backend.app.elexon import build_fuelhh_params, build_windfor_params


class AnalysisTests(unittest.TestCase):
    def test_parse_datetime_normalises_to_utc(self):
        parsed = parse_datetime("2026-01-01T01:00:00+01:00")
        self.assertEqual(parsed, datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc))

    def test_extract_rows_supports_array_and_envelope(self):
        rows = [{"generation": 1}]
        self.assertEqual(extract_rows(rows), rows)
        self.assertEqual(extract_rows({"data": rows}), rows)
        self.assertEqual(extract_rows({"unexpected": rows}), [])

    def test_aggregates_two_half_hour_actuals_to_arithmetic_mean(self):
        # Period 21 (10:00) = 100 MW, Period 22 (10:30) = 200 MW -> Mean = 150 MW
        actuals = [
            {"fuelType": "WIND", "startTime": "2026-01-02T10:00:00Z", "settlementPeriod": 21, "generation": 100},
            {"fuelType": "WIND", "startTime": "2026-01-02T10:30:00Z", "settlementPeriod": 22, "generation": 200},
        ]
        forecasts = [
            {"startTime": "2026-01-02T10:00:00Z", "publishTime": "2026-01-01T08:00:00Z", "generation": 160},
        ]
        result = build_analysis(actuals, forecasts, horizon_hours=24)
        self.assertEqual(result["coverage"]["matched_hours"], 1)
        interval = result["intervals"][0]
        self.assertEqual(interval["actual_mw"], 150.0)
        self.assertEqual(interval["forecast_mw"], 160.0)
        self.assertEqual(interval["error_mw"], 10.0)
        self.assertEqual(interval["half_hour_count"], 2)
        self.assertEqual(interval["settlement_periods"], [21, 22])
        self.assertEqual(result["metrics"]["mae_mw"], 10.0)

    def test_handles_incomplete_half_hour_actual_record(self):
        # Hour 10:00 has only one half-hour record (10:00).
        # It is incomplete: excluded from primary accuracy scoring to avoid misleading metrics.
        actuals = [
            {"fuelType": "WIND", "startTime": "2026-01-02T10:00:00Z", "settlementPeriod": 21, "generation": 100},
        ]
        forecasts = [
            {"startTime": "2026-01-02T10:00:00Z", "publishTime": "2026-01-01T08:00:00Z", "generation": 105},
        ]
        result = build_analysis(actuals, forecasts, horizon_hours=24)
        self.assertEqual(result["coverage"]["complete_actual_hours"], 0)
        self.assertEqual(result["coverage"]["incomplete_actual_hours"], 1)
        self.assertEqual(result["coverage"]["matched_hours"], 0)
        self.assertEqual(len(result["intervals"]), 0)
        self.assertIsNone(result["metrics"]["mae_mw"])
        self.assertEqual(len(result["incomplete_hours"]), 1)
        self.assertEqual(result["incomplete_hours"][0]["time"], "2026-01-02T10:00:00Z")

    def test_incomplete_hour_does_not_contaminate_accuracy_metrics(self):
        # Hour 10:00 is complete (100 MW, 200 MW -> mean 150 MW vs 150 MW forecast -> error = 0 MW)
        # Hour 11:00 is incomplete (only 11:00 is present, massive forecast miss 500 MW vs 0 MW)
        # The incomplete hour must be excluded so MAE remains 0.0 MW.
        actuals = [
            {"fuelType": "WIND", "startTime": "2026-01-02T10:00:00Z", "generation": 100},
            {"fuelType": "WIND", "startTime": "2026-01-02T10:30:00Z", "generation": 200},
            {"fuelType": "WIND", "startTime": "2026-01-02T11:00:00Z", "generation": 0},
            # 11:30 is missing!
        ]
        forecasts = [
            {"startTime": "2026-01-02T10:00:00Z", "publishTime": "2026-01-01T08:00:00Z", "generation": 150},
            {"startTime": "2026-01-02T11:00:00Z", "publishTime": "2026-01-01T08:00:00Z", "generation": 500},
        ]
        result = build_analysis(actuals, forecasts, horizon_hours=24)
        self.assertEqual(result["coverage"]["complete_actual_hours"], 1)
        self.assertEqual(result["coverage"]["incomplete_actual_hours"], 1)
        self.assertEqual(result["coverage"]["matched_hours"], 1)
        self.assertEqual(len(result["intervals"]), 1)
        self.assertEqual(result["intervals"][0]["time"], "2026-01-02T10:00:00Z")
        self.assertEqual(result["metrics"]["mae_mw"], 0.0)

    def test_hours_classification_complete_incomplete_missing(self):
        # Hour 10:00 has both records (complete)
        # Hour 11:00 has 1 record (incomplete)
        # Remaining 742 hours have 0 records (missing)
        actuals = [
            {"fuelType": "WIND", "startTime": "2026-01-02T10:00:00Z", "generation": 100},
            {"fuelType": "WIND", "startTime": "2026-01-02T10:30:00Z", "generation": 100},
            {"fuelType": "WIND", "startTime": "2026-01-02T11:00:00Z", "generation": 100},
        ]
        result = build_analysis(actuals, [], horizon_hours=24)
        cov = result["coverage"]
        self.assertEqual(cov["expected_hours"], 744)
        self.assertEqual(cov["complete_actual_hours"], 1)
        self.assertEqual(cov["incomplete_actual_hours"], 1)
        self.assertEqual(cov["missing_actual_hours"], 742)
        self.assertEqual(cov["matched_hours"], 0)

    def test_matches_correct_hourly_forecast(self):
        # Two distinct hours: 10:00 and 11:00
        actuals = [
            {"fuelType": "WIND", "startTime": "2026-01-02T10:00:00Z", "generation": 100},
            {"fuelType": "WIND", "startTime": "2026-01-02T10:30:00Z", "generation": 100},
            {"fuelType": "WIND", "startTime": "2026-01-02T11:00:00Z", "generation": 200},
            {"fuelType": "WIND", "startTime": "2026-01-02T11:30:00Z", "generation": 200},
        ]
        forecasts = [
            {"startTime": "2026-01-02T10:00:00Z", "publishTime": "2026-01-01T08:00:00Z", "generation": 105},
            {"startTime": "2026-01-02T11:00:00Z", "publishTime": "2026-01-01T08:00:00Z", "generation": 210},
        ]
        result = build_analysis(actuals, forecasts, horizon_hours=24)
        self.assertEqual(result["coverage"]["matched_hours"], 2)
        self.assertEqual(result["intervals"][0]["time"], "2026-01-02T10:00:00Z")
        self.assertEqual(result["intervals"][0]["forecast_mw"], 105.0)
        self.assertEqual(result["intervals"][1]["time"], "2026-01-02T11:00:00Z")
        self.assertEqual(result["intervals"][1]["forecast_mw"], 210.0)

    def test_excludes_forecasts_published_after_horizon_cutoff(self):
        actuals = [
            {"fuelType": "WIND", "startTime": "2026-01-02T12:00:00Z", "generation": 100},
            {"fuelType": "WIND", "startTime": "2026-01-02T12:30:00Z", "generation": 100},
        ]
        forecasts = [
            # Published 23h before target (cutoff for 24h lead time is 2026-01-01T12:00:00Z)
            {"startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-01T13:00:00Z", "generation": 150},
        ]
        result = build_analysis(actuals, forecasts, horizon_hours=24)
        self.assertEqual(result["coverage"]["matched_hours"], 0)
        self.assertEqual(result["coverage"]["hours_without_eligible_forecast"], 1)

    def test_selects_latest_eligible_forecast_revision(self):
        actuals = [
            {"fuelType": "WIND", "startTime": "2026-01-02T12:00:00Z", "generation": 100},
            {"fuelType": "WIND", "startTime": "2026-01-02T12:30:00Z", "generation": 100},
        ]
        forecasts = [
            {"startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-01T08:00:00Z", "generation": 80},
            {"startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-01T11:00:00Z", "generation": 90},
            # Published after 24h cutoff
            {"startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-01T12:00:01Z", "generation": 110},
        ]
        result = build_analysis(actuals, forecasts, horizon_hours=24)
        self.assertEqual(result["coverage"]["matched_hours"], 1)
        self.assertEqual(result["intervals"][0]["forecast_mw"], 90.0)

    def test_hourly_energy_mwh_multiplier_is_one(self):
        # 1-hour interval with error of 50 MW must equal 50.0 MWh (not 25.0 MWh)
        actuals = [
            {"fuelType": "WIND", "startTime": "2026-01-02T12:00:00Z", "generation": 100},
            {"fuelType": "WIND", "startTime": "2026-01-02T12:30:00Z", "generation": 100},
        ]
        forecasts = [
            {"startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-01T10:00:00Z", "generation": 150},
        ]
        result = build_analysis(actuals, forecasts, horizon_hours=24)
        self.assertEqual(result["metrics"]["forecast_minus_actual_mwh"], 50.0)
        self.assertEqual(result["metrics"]["absolute_error_mwh"], 50.0)

    def test_zero_matches_and_zero_actual_cases_safe(self):
        # Zero matches
        result_empty = build_analysis([], [], horizon_hours=24)
        self.assertEqual(result_empty["coverage"]["matched_hours"], 0)
        self.assertIsNone(result_empty["metrics"]["mae_mw"])
        self.assertIsNone(result_empty["metrics"]["rmse_mw"])
        self.assertIsNone(result_empty["metrics"]["bias_mw"])
        self.assertIsNone(result_empty["metrics"]["wape_pct"])
        self.assertEqual(result_empty["metrics"]["forecast_minus_actual_mwh"], 0.0)
        self.assertEqual(result_empty["metrics"]["absolute_error_mwh"], 0.0)

        # Zero total actual generation -> WAPE should be None without ZeroDivisionError
        actuals_zero = [
            {"fuelType": "WIND", "startTime": "2026-01-02T12:00:00Z", "generation": 0},
            {"fuelType": "WIND", "startTime": "2026-01-02T12:30:00Z", "generation": 0},
        ]
        forecasts = [
            {"startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-01T10:00:00Z", "generation": 10},
        ]
        result_zero = build_analysis(actuals_zero, forecasts, horizon_hours=24)
        self.assertEqual(result_zero["coverage"]["matched_hours"], 1)
        self.assertIsNone(result_zero["metrics"]["wape_pct"])
        self.assertEqual(result_zero["metrics"]["mae_mw"], 10.0)

    def test_january_1_and_january_31_boundaries(self):
        # First hour of month: Jan 1 00:00 UTC (periods 1 & 2)
        # Last hour of month: Jan 31 23:00 UTC (periods 47 & 48)
        actuals = [
            {"fuelType": "WIND", "startTime": "2026-01-01T00:00:00Z", "settlementPeriod": 1, "generation": 50},
            {"fuelType": "WIND", "startTime": "2026-01-01T00:30:00Z", "settlementPeriod": 2, "generation": 50},
            {"fuelType": "WIND", "startTime": "2026-01-31T23:00:00Z", "settlementPeriod": 47, "generation": 80},
            {"fuelType": "WIND", "startTime": "2026-01-31T23:30:00Z", "settlementPeriod": 48, "generation": 80},
        ]
        forecasts = [
            {"startTime": "2026-01-01T00:00:00Z", "publishTime": "2025-12-30T10:00:00Z", "generation": 55},
            {"startTime": "2026-01-31T23:00:00Z", "publishTime": "2026-01-30T10:00:00Z", "generation": 85},
        ]
        result = build_analysis(actuals, forecasts, horizon_hours=24)
        self.assertEqual(result["coverage"]["matched_hours"], 2)
        times = [r["time"] for r in result["intervals"]]
        self.assertIn("2026-01-01T00:00:00Z", times)
        self.assertIn("2026-01-31T23:00:00Z", times)

    def test_duplicate_actual_with_missing_then_valid_publish_time_does_not_crash(self):
        actuals = [
            {"fuelType": "WIND", "startTime": "2026-01-02T12:00:00Z", "generation": 100, "publishTime": None},
            {"fuelType": "WIND", "startTime": "2026-01-02T12:00:00Z", "generation": 105, "publishTime": "2026-01-02T12:30:00Z"},
            {"fuelType": "WIND", "startTime": "2026-01-02T12:30:00Z", "generation": 105, "publishTime": "2026-01-02T12:30:00Z"},
        ]
        forecasts = [
            {"startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-01T10:00:00Z", "generation": 105},
        ]
        result = build_analysis(actuals, forecasts, horizon_hours=24)
        self.assertEqual(result["coverage"]["matched_hours"], 1)
        self.assertEqual(result["intervals"][0]["actual_mw"], 105.0)

    def test_duplicate_actual_preserves_timestamped_over_untimestamped(self):
        actuals = [
            {"fuelType": "WIND", "startTime": "2026-01-02T12:00:00Z", "generation": 105, "publishTime": "2026-01-02T12:30:00Z"},
            {"fuelType": "WIND", "startTime": "2026-01-02T12:00:00Z", "generation": 100, "publishTime": None},
            {"fuelType": "WIND", "startTime": "2026-01-02T12:30:00Z", "generation": 105, "publishTime": "2026-01-02T12:30:00Z"},
        ]
        forecasts = [
            {"startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-01T10:00:00Z", "generation": 105},
        ]
        result = build_analysis(actuals, forecasts, horizon_hours=24)
        self.assertEqual(result["coverage"]["matched_hours"], 1)
        self.assertEqual(result["intervals"][0]["actual_mw"], 105.0)

    def test_rejects_invalid_horizon(self):
        with self.assertRaises(ValueError):
            build_analysis([], [], horizon_hours=0)

    def test_build_fuelhh_params_covers_full_month(self):
        params = build_fuelhh_params("2026-01")
        self.assertEqual(params["settlementDateFrom"], "2026-01-01")
        self.assertEqual(params["settlementDateTo"], "2026-01-31")
        self.assertEqual(params["fuelType"], "WIND")
        self.assertNotIn("from", params)
        self.assertNotIn("to", params)

    def test_build_windfor_params_uses_documented_names(self):
        params = build_windfor_params("2026-01", max_horizon_hours=168)
        self.assertEqual(params["publishDateTimeFrom"], "2025-12-24T00:00:00Z")
        self.assertEqual(params["publishDateTimeTo"], "2026-02-01T00:00:00Z")
        self.assertNotIn("from", params)
        self.assertNotIn("to", params)

    def test_param_builders_reject_invalid_month(self):
        for bad_month in ["2026-13", "invalid", "", "2026/01"]:
            with self.assertRaises(ValueError):
                build_fuelhh_params(bad_month)
            with self.assertRaises(ValueError):
                build_windfor_params(bad_month)

    def test_retrospective_forecast_published_after_target_is_rejected(self):
        actuals = [
            {"fuelType": "WIND", "startTime": "2026-01-02T12:00:00Z", "generation": 100},
            {"fuelType": "WIND", "startTime": "2026-01-02T12:30:00Z", "generation": 100},
        ]
        forecasts = [
            {"startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-02T14:00:00Z", "generation": 100},
        ]
        result = build_analysis(actuals, forecasts, horizon_hours=24)
        self.assertEqual(result["coverage"]["matched_hours"], 0)
        self.assertEqual(result["coverage"]["hours_without_eligible_forecast"], 1)

    def test_forecast_lead_time_exceeding_publication_horizon_is_unmatched(self):
        actuals = [
            {"fuelType": "WIND", "startTime": "2026-01-04T00:00:00Z", "generation": 100},
            {"fuelType": "WIND", "startTime": "2026-01-04T00:30:00Z", "generation": 100},
        ]
        forecasts = [
            {"startTime": "2026-01-04T00:00:00Z", "publishTime": "2026-01-02T00:00:00Z", "generation": 95},  # 48h lead
        ]
        result_24 = build_analysis(actuals, forecasts, horizon_hours=24)
        self.assertEqual(result_24["coverage"]["matched_hours"], 1)

        result_72 = build_analysis(actuals, forecasts, horizon_hours=72)
        self.assertEqual(result_72["coverage"]["matched_hours"], 0)
        self.assertEqual(result_72["coverage"]["hours_without_eligible_forecast"], 1)

    def test_coverage_reporting_keys_and_values(self):
        actuals = [
            {"fuelType": "WIND", "startTime": "2026-01-02T10:00:00Z", "generation": 100},
            {"fuelType": "WIND", "startTime": "2026-01-02T10:30:00Z", "generation": 100},
        ]
        forecasts = [
            {"startTime": "2026-01-02T10:00:00Z", "publishTime": "2026-01-01T08:00:00Z", "generation": 100},
        ]
        result = build_analysis(actuals, forecasts, horizon_hours=24)
        cov = result["coverage"]
        self.assertEqual(cov["expected_hours"], 744)
        self.assertEqual(cov["complete_actual_hours"], 1)
        self.assertEqual(cov["incomplete_actual_hours"], 0)
        self.assertEqual(cov["actual_hours"], 1)
        self.assertEqual(cov["matched_hours"], 1)
        self.assertEqual(cov["missing_actual_hours"], 743)
        self.assertEqual(cov["hours_without_eligible_forecast"], 0)
        self.assertEqual(cov["actual_coverage_pct"], round(1 / 744 * 100, 2))
        self.assertEqual(cov["forecast_match_pct_of_actuals"], 100.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
