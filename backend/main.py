import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db import init_db
from redis_client import close_redis
from api.rest import router as rest_router
from api.websocket import router as ws_router
from api.position import router as position_router
from data.scheduler import start_scheduler, stop_scheduler
from data.hyperliquid_ws import run_hyperliquid_ws
# Engine loop removed — signals are generated on-demand via POST /api/signal/refresh
# Data fetchers (macro, sentiment, etc.) still run on schedule so data is fresh

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()
    ws_task = asyncio.create_task(run_hyperliquid_ws())
    yield
    ws_task.cancel()
    stop_scheduler()
    await close_redis()

app = FastAPI(title="BTC Trading Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://btc-dashboard-frontend-k5a3.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rest_router)
app.include_router(ws_router)
app.include_router(position_router)

@app.get("/health")
async def health():
    return {"status": "ok"}
