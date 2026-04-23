import aiosqlite
from config import settings

DB_PATH = settings.sqlite_path

async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db

async def init_db():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS candles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            timeframe TEXT NOT NULL,
            UNIQUE(timestamp, timeframe)
        );
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            direction TEXT NOT NULL,
            composite_score REAL NOT NULL,
            strength TEXT NOT NULL,
            entry_low REAL NOT NULL,
            entry_high REAL NOT NULL,
            stop_loss REAL NOT NULL,
            take_profit_1 REAL NOT NULL,
            take_profit_2 REAL NOT NULL,
            recommended_leverage INTEGER NOT NULL,
            liquidation_price REAL NOT NULL,
            risk_reward_ratio REAL NOT NULL,
            confluence_count INTEGER NOT NULL,
            votes_json TEXT NOT NULL,
            warnings_json TEXT NOT NULL,
            outcome TEXT,
            actual_pnl_pct REAL,
            closed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_price REAL NOT NULL,
            size REAL NOT NULL,
            leverage INTEGER NOT NULL,
            direction TEXT NOT NULL,
            entry_time TEXT NOT NULL,
            accumulated_funding REAL DEFAULT 0.0,
            closed_at TEXT,
            close_price REAL,
            pnl REAL
        );
        CREATE INDEX IF NOT EXISTS idx_candles_tf_ts ON candles(timeframe, timestamp);
        CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(timestamp);
    """)
    await db.commit()
    await db.close()
