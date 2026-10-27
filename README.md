# WindSignal — UK Wind Forecast Monitor

A React + FastAPI pilot application for evaluating national Great Britain wind-generation forecasts against actual generation for **January 2026**, using the public Elexon Insights Solution datasets (`FUELHH` and `WINDFOR`).

[![Tests](https://img.shields.io/badge/tests-21%20passed-brightgreen)](#running-tests)
[![Python](https://img.shields.io/badge/python-3.12-blue)](backend/)
[![React](https://img.shields.io/badge/react-18.3-blue)](frontend/)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](Dockerfile)

---

## Deployment Links (Placeholders)

- **Public GitHub Repository:** `https://github.com/ANONYMOUS_USER/wind-forecast-challenge` *(To be populated upon publication)*
- **Live Deployment:** `https://YOUR-APP.vercel.app` *(To be populated upon deployment)*

---

## What It Does

- **National Wind Forecast Evaluation:** Compares hourly forecast publications against transmission-metered actual outturn for January 2026.
- **Completeness-Gated Hourly Aggregation:** Natively bridges the temporal resolution difference between 30-minute settlement actuals (`FUELHH`) and 60-minute target forecasts (`WINDFOR`) by computing arithmetic hourly means across complete settlement pairs (`:00` and `:30`). Incomplete hours are strictly excluded from accuracy scoring.
- **Configurable Horizon Gate-Closure Rule:** To avoid hindsight bias, evaluates forecasts published at or before `startTime - selected lead time` (12h, 24h, 36h, 48h, 60h). Retrospective records (`publishTime > startTime`) are excluded.
- **Comprehensive Accuracy Metrics:** Calculates Mean Absolute Error (MAE), Root Mean Square Error (RMSE), Forecast Bias, Weighted Absolute Percentage Error (WAPE), and Net Volume Energy Error (MWh).
- **Transparent Coverage Tracking:** Distinguishes expected hours (744), complete actual hours (744 in January 2026), incomplete hours, missing actuals, and intervals lacking eligible forecasts.
- **Fail-Safe Operation:** Fails visibly with explicit HTTP 502/500 errors and UI alerts when external APIs fail; never fabricates or quietly substitutes fake placeholder numbers.

---

## Data Sources & Methodology

1. **Actual Generation (`FUELHH`):**
   - Source: [Elexon FUELHH stream](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream)
   - Filtered for `fuelType = WIND`.
   - Queried using documented `settlementDateFrom=2026-01-01` and `settlementDateTo=2026-01-31` (inclusive, covering all 48 settlement periods each day).
2. **Forecast Generation (`WINDFOR`):**
   - Source: [Elexon WINDFOR stream](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream)
   - Queried using documented `publishDateTimeFrom` and `publishDateTimeTo` (ISO-8601 UTC).
   - Forecast targets are published at 1-hour intervals (`:00`).
3. **Hourly Aggregation Model:**
   - Great Britain settlement periods occur every 30 minutes ($T\text{:00}$ and $T\text{:30}$), whereas WINDFOR forecasts target the whole hour ($T\text{:00}$).
   - For every hour $T$, the actual generation is evaluated as:
     $$\text{Actual}_{\text{hour}} = \frac{\text{Actual}_{T:00} + \text{Actual}_{T:30}}{2}$$
   - An hour is considered complete only if both half-hour settlement records are present.
   - Energy error metrics in MWh use the correct 1.0-hour multiplier:
     $$\text{Energy Error (MWh)} = 1.0 \times \sum (F_i - A_i)$$

---

## Observed Real-Data Metrics (January 2026, 24h Horizon)

Across the full January 2026 sample (744/744 hours matched, 100.0% coverage):

| Metric | Observed Value | Interpretation |
| :--- | :--- | :--- |
| **MAE** | **2,064.14 MW** | Average magnitude of forecast error per hour |
| **RMSE** | **2,524.28 MW** | Penalises large peak misses |
| **Forecast Bias** | **+1,854.60 MW** | Systemic overforecasting across January 2026 |
| **WAPE** | **17.82%** | Total absolute error divided by total actual output |
| **Net Energy Error** | **+1,379,820.50 MWh** | Net energy overforecast across the month |
| **Directional Splits** | **648 overforecast / 96 underforecast** | Forecasts ran higher than actuals in 87.1% of hours |

---

## Supported Horizons & Feed Limitations

| Horizon | Jan 2026 Matched Hours | Coverage (%) | Status | Analytical Notes |
| :---: | :---: | :---: | :---: | :--- |
| **12h** | 744 / 744 | **100.0%** | Active | Full day-ahead short-term evaluation |
| **24h** | 744 / 744 | **100.0%** | Active | Baseline day-ahead market proxy |
| **36h** | 744 / 744 | **100.0%** | Active | Medium-range evaluation |
| **48h** | 589 / 744 | **79.2%** | Active | Earliest days in month lack $\ge 48$h publications |
| **60h** | 217 / 744 | **29.2%** | Active | Publications taper past 48h |
| **72h** | **0 / 744** | **0.0%** | Disabled in UI | Elexon WINDFOR feed lookahead caps at **66.5 hours** |

---

## Repository Layout

```text
.
├── backend/
│   ├── app/
│   │   ├── __init__.py       # Python package marker
│   │   ├── analysis.py       # Pure aggregation, matching, and scoring logic
│   │   ├── elexon.py         # HTTP client with documented query params & TTL cache
│   │   └── main.py           # FastAPI routes, CORS, and static file serving
│   ├── tests/
│   │   ├── __init__.py       # Tests package marker
│   │   └── test_analysis.py  # 21 unit tests covering edge cases & scoring
│   ├── check_elexon.py       # Live diagnostic script for inspecting real responses
│   ├── index.py              # Serverless entrypoint (Vercel)
│   ├── requirements.txt      # FastAPI, Uvicorn, Requests
│   └── .python-version       # Python 3.12
├── frontend/
│   ├── src/
│   │   ├── api.js            # API fetch client
│   │   ├── App.jsx           # Dashboard UI with Recharts and Lucide icons
│   │   ├── main.jsx          # React DOM entrypoint
│   │   └── styles.css        # Responsive dark UI theme
│   ├── index.html
│   ├── package.json          # React 18, Vite 6, Recharts 2
│   └── vite.config.js        # Vite dev server + /api proxy
├── Dockerfile                # Multi-stage build (Node 20 build -> Python 3.12 runtime)
├── docker-compose.yml        # One-command container orchestration
├── .env.example              # Safe environment variable defaults
├── .gitignore                # Release-ready ignore rules
├── ANTIGRAVITY_TASKS.md      # Engineering task tracking
├── VIDEO_SCRIPT.md           # 10-minute hiring presentation script
└── README.md
```

---

## Prerequisites

- **Python:** 3.12 or newer
- **Node.js:** 20.x or newer with `npm`
- **Docker:** Docker Desktop (if running via container)

---

## Running with Docker Compose (Recommended)

To build both frontend and backend and run the unified service in Docker:

```bash
docker compose up --build
```

- Open the dashboard at [http://localhost:8000](http://localhost:8000).
- Health check: [http://localhost:8000/health](http://localhost:8000/health)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Live JSON analysis: `http://localhost:8000/api/analysis?month=2026-01&horizon_hours=24`

---

## Running Locally Without Docker

### Terminal 1 — Backend (FastAPI)

```powershell
cd backend
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Terminal 2 — Frontend (React / Vite)

```powershell
cd frontend
npm install
npm run dev
```

Open the printed Vite URL (typically `http://localhost:5173`). Vite proxies API requests to `http://127.0.0.1:8000`.

---

## Running Tests and Diagnostics

### Run the Backend Unit Tests (Offline)

All 21 analytical and parameter-building unit tests execute offline without network dependencies:

```powershell
# From repository root:
python -m unittest discover -s backend/tests -v
```

### Run the Live Elexon API Diagnostic

Queries the live Elexon API, validates query parameters, prints response schemas, row counts, and live scores:

```powershell
# Requires network access and installed backend requirements:
python -m backend.check_elexon
```

### Build the Frontend for Production

```powershell
cd frontend
npm run build
```

The production bundle is generated in `frontend/dist/`. In production or Docker, FastAPI automatically serves these static files from `frontend/dist/`.

---

## Known Limitations & Domain Context

1. **Embedded vs. Transmission Metering:**
   `FUELHH` records generation from transmission-connected wind farms. `WINDFOR` is National Grid ESO's transmission-visible forecast model. Differences in how embedded/unmetered distributed wind is modeled between datasets can introduce a baseline offset.
2. **Trading Gate Closure Approximation:**
   The challenge brief did not specify an exact market gate-closure timestamp. A fixed lead-time rule ($T - H$) is used as a transparent, auditable proxy. In a live trading desk, this should be replaced by the formal day-ahead auction deadline (e.g. 11:00 or 12:00 day-ahead).
3. **Process-Local Caching:**
   Raw Elexon payloads are cached in memory for 15 minutes (`ELEXON_CACHE_TTL_SECONDS=900`) per process. For a multi-instance production deployment, Redis or Memcached should be used.

---

## AI Tools Disclosure

In accordance with academic and professional honesty standards:
- **ChatGPT (OpenAI):** Used during initial project scaffolding for high-level requirement breakdown and initial file structure drafting.
- **Google Antigravity:** Used for codebase inspection, Elexon API query-parameter diagnosis (`settlementDateFrom`/`publishDateTimeFrom`), resolving a subtle `TypeError` in duplicate actuals resolution, designing the completeness-gated hourly aggregation model, expanding the unit test suite to 21 passing regression tests, diagnosing horizon publication lookahead limits (66.5h cap), and verifying production build readiness.
- All code changes, tests, and API interactions were independently audited, executed, and validated against live Elexon data.

---

## License

This project was developed as a hiring technical challenge and is provided for evaluation purposes.
