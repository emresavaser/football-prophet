# Football Prophet

Football Prophet is a football prediction and value-betting system with:

- ensemble match prediction
- odds ingestion and odds history
- value bet detection
- bet settlement and CLV tracking
- backtest reporting
- FastAPI dashboard and CLI flows

## Repo Workflow

Primary branches:

- `main`
- `codex/person-a-engine-data`
- `codex/person-b-api-product`

Recommended flow:

1. Pull latest `main`
2. Work only on your branch
3. Run tests before each push
4. Open PR into `main`

## Local Setup

Requirements:

- Python 3.12+ preferred
- PowerShell on Windows is supported

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Copy environment template:

```powershell
Copy-Item env.example .env
```

## Run Tests

```powershell
python -m unittest discover -s tests -v
```

## Run API

```powershell
python -c "from api.app import create_app; import uvicorn; uvicorn.run(create_app(), host='127.0.0.1', port=8000)"
```

Available URLs:

- API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Dashboard: [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)
- Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

## Run CLI

Main entry:

```powershell
python main.py
```

## Backtest API

Recent backtests:

- `GET /api/backtests`

Single backtest detail:

- `GET /api/backtests/{run_id}`

These endpoints expose:

- summary metrics
- config snapshot
- model weights
- market breakdown
- bet summary payload

## Dashboard Notes

The dashboard now includes:

- live prediction table
- value bet panel with status and market filters
- live ROI summary
- backtest runs list
- backtest detail panel
- market-level backtest breakdown

## Ownership Split

Person A:

- model/training/calibration/data/backtest engine

Person B:

- API/dashboard/frontend/docs

Avoid unplanned cross-branch edits in:

- `data/models.py`
- `data/database.py`
- `api/schemas/*`

If these contracts must change, align first.
