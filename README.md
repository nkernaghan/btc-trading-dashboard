# BTC Leverage Dashboard

A Bitcoin long/short position indicator. FastAPI backend pulls market data and derives signals; Next.js frontend renders the dashboard.

## What's inside

- `backend/` — FastAPI + APScheduler + SQLite + Redis. Pulls from Coinglass, Coinalyze, Glassnode, Binance, Hyperliquid (WS), ETFs, news. Produces composite long/short signals.
- `frontend/` — Next.js 14 + Tailwind + lightweight-charts. Terminal-style dark UI.
- `docker-compose.yml` — one-command run for all three services (backend, frontend, Redis).
- `.env.example` — copy to `.env` and fill in API keys.

Most API keys are optional. The app runs on free data sources if they're missing; signals that need a paid key just won't populate.

## Quick start (Docker — recommended)

You need Docker Desktop running.

```bash
cp .env.example .env        # then edit and add any API keys you have
docker compose up --build
```

Open http://localhost:3000. The backend API is at http://localhost:8000 (health check: `/health`).

First boot takes 2–3 minutes while Docker pulls images and installs dependencies.

## Manual run (no Docker)

Three terminals.

**1. Redis**
```bash
brew install redis && brew services start redis
```

**2. Backend**
```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
# edit .env: set REDIS_URL=redis://localhost:6379/0
uvicorn main:app --reload --port 8000
```

**3. Frontend**
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

## API keys

All optional. Add them to `.env` to unlock the corresponding data sources:

- `COINGLASS_API_KEY` — funding rates, liquidations, open interest
- `GLASSNODE_API_KEY` — on-chain metrics
- `CRYPTOQUANT_API_KEY` — exchange flows
- `NEWSAPI_KEY` — news sentiment
- `DERIBIT_CLIENT_ID` / `DERIBIT_CLIENT_SECRET` — options flow
- `COINGECKO_API_KEY` — higher rate limits for price data

## Ports

- 3000 — frontend
- 8000 — backend (REST + WebSocket at `/ws`)
- 6379 — Redis

## Stopping

```bash
docker compose down        # stops containers, keeps Redis data
docker compose down -v     # also wipes Redis volume
```
