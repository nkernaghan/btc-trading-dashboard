export type Direction = 'LONG' | 'SHORT' | 'WAIT';
export type VoteType = 'STRONG_LONG' | 'LONG' | 'NEUTRAL' | 'SHORT' | 'STRONG_SHORT';
export type SignalStrength = 'STRONG' | 'MODERATE' | 'WEAK' | 'NONE';
export type Session = 'ASIA' | 'LONDON' | 'NEW_YORK' | 'OVERLAP';
export type Timeframe = '1H' | '4H' | '1D' | '1W';

export interface IndicatorVote {
  name: string;
  category: string;
  vote: VoteType;
  value: number | string;
  weight: number;
  details?: string;
}

export interface Signal {
  direction: Direction;
  strength: SignalStrength;
  composite_score: number;
  confluence: number;
  total_indicators: number;
  entry: number;
  stop_loss: number;
  take_profit_1: number;
  take_profit_2: number;
  leverage: number;
  liquidation_price: number;
  risk_reward: number;
  warnings: string[];
  votes: IndicatorVote[];
  timestamp: string;
}

export interface Position {
  id: string;
  direction: Direction;
  leverage: number;
  entry_price: number;
  current_price: number;
  pnl_pct: number;
  pnl_usd: number;
  liquidation_price: number;
  distance_to_liq_pct: number;
  funding_paid: number;
  breakeven: number;
  opened_at: string;
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface OrderBook {
  bids: [number, number][];
  asks: [number, number][];
  spread: number;
  mid_price: number;
}

export interface DashboardData {
  price: number;
  price24hChange: number;
  high24h: number;
  low24h: number;
  fundingRate: number;
  openInterest: number;
  oiDelta: number;
  candles: Candle[];
  timeframe: Timeframe;
  signal: Signal | null;
  votes: IndicatorVote[];
  warnings: string[];
  position: Position | null;
  orderbook: OrderBook | null;
  indicators: Record<string, IndicatorVote[]>;
}
