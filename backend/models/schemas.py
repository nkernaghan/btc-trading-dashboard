from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from .enums import Direction, VoteType, SignalStrength, Session, Timeframe, IndicatorCategory

class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: Timeframe

class IndicatorVote(BaseModel):
    name: str
    category: IndicatorCategory
    vote: VoteType
    strength: int
    value: float
    description: str

class Signal(BaseModel):
    timestamp: datetime
    direction: Direction
    composite_score: float
    strength: SignalStrength
    entry_low: float
    entry_high: float
    stop_loss: float
    stop_loss_pct: float
    take_profit_1: float
    take_profit_1_pct: float
    take_profit_2: float
    take_profit_2_pct: float
    recommended_leverage: int
    liquidation_price: float
    risk_reward_ratio: float
    confluence_count: int
    votes: list[IndicatorVote]
    warnings: list[str]

class Position(BaseModel):
    entry_price: float
    size: float
    leverage: int
    direction: Direction
    entry_time: datetime
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    liquidation_price: Optional[float] = None
    distance_to_liq_pct: Optional[float] = None
    accumulated_funding: Optional[float] = None
    breakeven_price: Optional[float] = None

class DashboardState(BaseModel):
    price: float
    price_24h_change_pct: float
    high_24h: float
    low_24h: float
    funding_rate: float
    next_funding_time: datetime
    open_interest: float
    oi_delta_pct: float
    session: Session
    signal: Optional[Signal]
    votes: list[IndicatorVote]
    position: Optional[Position]
    warnings: list[str]

class BacktestRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    min_confidence: float = 70.0
    max_leverage: int = 40

class BacktestResult(BaseModel):
    total_trades: int
    win_rate: float
    avg_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    profit_factor: float
    equity_curve: list[float]
    signals: list[Signal]

class SignalRecord(BaseModel):
    id: Optional[int] = None
    signal: Signal
    outcome: Optional[str] = None
    actual_pnl_pct: Optional[float] = None
    closed_at: Optional[datetime] = None
