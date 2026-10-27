# Antigravity work plan — follow in order

Do not ask Antigravity to rewrite the entire application in one prompt. Keep the starter structure, ask it to make minimal changes, and review the diff after each task.

## Task 1 — verify structure and requirements

> Read `README.md`, the challenge brief, and the complete codebase. Do not edit files yet. Summarise the architecture, user workflows, forecast selection rule, metrics, and assumptions. Identify likely API schema/query-parameter risks in the Elexon WINDFOR and FUELHH stream calls. Do not assert the real API has been verified unless you actually execute a request and inspect the response.

## Task 2 — test and fix the backend

> From the repository root, run `python -m unittest discover -s backend/tests -v`. Then create/use a Python 3.12 virtual environment, install `backend/requirements.txt`, and start the FastAPI service. Run `python -m backend.check_elexon` to inspect the actual Elexon response schema and row counts. Inspect `/health`, `/docs`, and `/api/analysis?month=2026-01&horizon_hours=24`. If real Elexon calls fail, inspect the documented endpoint and response carefully, make the smallest targeted fix in `backend/app/elexon.py`, and add a regression test. Do not hardcode, generate, or quietly substitute fake metrics.

## Task 3 — verify forecast-selection correctness

> Audit `backend/app/analysis.py`. Prove with tests that the latest eligible `publishTime` is selected, records published after the cutoff are excluded, UTC offsets are normalised, non-WIND actuals are excluded, missing forecasts are surfaced in coverage, and metrics use matched rows only. Add tests for duplicate target timestamps and empty data. Do not change the lead-time definition without updating README and tests.

## Task 4 — run the frontend

> Run `npm install` and `npm run build` inside `frontend/`. Start the backend and Vite frontend, check browser console and network requests, and fix only verified defects. Preserve the existing responsive design and do not add mock data to make the dashboard appear populated. When the API fails, the UI must display the error clearly.

## Task 5 — end-to-end and Docker

> Build the project with `docker compose up --build`, verify the dashboard at `http://localhost:8000`, check `/health` and `/api/analysis`, and inspect container logs. If Docker or the real API cannot be run in this environment, state that explicitly instead of claiming success. Do not expose secrets or add unnecessary dependencies.

## Task 6 — pre-submission review

> Review the whole repository as a senior engineer. Report findings by severity: correctness, API/data semantics, tests, security, deployment, documentation, and presentation. Confirm the README AI disclosure matches what actually happened. Do not claim it is production trading software. List every remaining manual action needed before submission and do not edit code without showing the proposed diff first.
