# Video plan (10 minutes maximum)

Do not record until the live app is deployed and tested with real Elexon data. Replace every bracketed item below with observed facts from your run.

## Part 1 — customer overview (target 4:30)

**0:00–0:30 — Business problem**
“Wind generation uncertainty changes how much non-renewable power a utility may need to procure. This pilot helps a day-ahead buyer inspect published national wind forecasts and quantify how those forecasts compared with actual output.”

**0:30–1:15 — Scope and live data**
“This pilot uses the two datasets specified in the brief: FUELHH actual generation filtered to `WIND`, and WINDFOR forecast publications. The selected delivery period is January 2026. All timestamps are shown in UTC.”

**1:15–2:00 — Forecast availability rule**
“The lead-time control is set to [observed setting]. For each half-hour target, the system picks the latest forecast publication that existed at least [setting] hours before the interval. This is an explicit pilot assumption because the brief did not give the exact market gate-closure timestamp.”

**2:00–3:20 — Accuracy and coverage**
“Across [actual matched count] matched intervals, the observed MAE is [real value] MW, RMSE is [real value] MW, bias is [real value] MW, and WAPE is [real value]%. These metrics describe the matched sample only. The coverage strip shows missing actuals and intervals without an eligible forecast so incomplete data does not disappear from view.”

**3:20–4:30 — Decision value and caveat**
“The value is traceability: a buyer can see the selected forecast, its publication time, the actual outturn and quantified error. This pilot does not claim to calculate residual demand or an optimal purchase quantity because demand, prices and thermal availability are outside the supplied data scope.”

## Part 2 — technical review (target 4:30)

**0:00–0:50 — Architecture**
“React and Recharts render the dashboard. A FastAPI backend retrieves Elexon data, caches raw responses for a short period, applies the forecast-selection rule, computes metrics and returns structured JSON. The app can run in Docker as one container; Vercel is documented as separate frontend and API projects.”

**0:50–1:50 — Data pipeline**
“FUELHH and WINDFOR are called through Elexon’s public dataset API. Timestamps are converted to UTC, actual and forecast rows are keyed by target `startTime`, and the forecast is selected using `publishTime` and the chosen lead time. Missing matches are tracked separately.”

**1:50–2:50 — Metric definitions**
“MAE is the mean absolute MW error; RMSE puts more weight on large misses; bias is forecast minus actual; WAPE normalises total absolute error by total actual output. We intentionally do not call 100 minus WAPE a universal accuracy score.”

**2:50–3:40 — Testing and reliability**
“Unit tests cover eligibility cutoffs, UTC normalisation, actual fuel filtering and missing forecasts. The API failure path returns a visible error rather than fabricating values. The cache is process-local and is adequate for a pilot, not a substitute for durable caching or monitoring.”

**3:40–4:30 — Limitations and next steps**
“The largest open assumption is whether the chosen lead-time rule exactly represents the client's day-ahead decision deadline. I would confirm the gate-closure timestamp with the trading team, verify historical publication semantics against source data, add persisted data-quality monitoring, and only add residual-demand or procurement recommendations if the client supplies the required demand and market inputs.”
