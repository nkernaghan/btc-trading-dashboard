export type Direction = 'LONG' | 'SHORT' | 'WAIT';
export type VoteType = 'BULL' | 'BEAR' | 'NEUTRAL' | 'WARN';
export type SignalStrength = 'STRONG' | 'WEAK' | 'NONE';
export type Session = 'ASIA' | 'LONDON' | 'NEW_YORK' | 'OVERLAP';
export type Timeframe = '1H' | '4H' | '1D' | '1W';

export interface IndicatorVote {
  name: string;
  category: string;
  vote: VoteType;
  strength: number;
  value: number;
  description: string;
}

export interface Signal {
  timestamp: string;
  direction: Direction;
  composite_score: number;
  strength: SignalStrength;
  entry_low: number;
  entry_high: number;
  stop_loss: number;
  stop_loss_pct: number;
  take_profit_1: number;
  take_profit_1_pct: number;
  take_profit_2: number;
  take_profit_2_pct: number;
  recommended_leverage: number;
  liquidation_price: number;
  risk_reward_ratio: number;
  confluence_count: number;
  votes: IndicatorVote[];
  warnings: string[];
  // Aliases from frontend components
  entry?: number;
  leverage?: number;
  risk_reward?: number;
  confluence?: number;
}

export interface Position {
  entry_price: number;
  size: number;
  leverage: number;
  direction: Direction;
  entry_time: string;
  current_price?: number;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
  liquidation_price?: number;
  distance_to_liq_pct?: number;
  accumulated_funding?: number;
  breakeven_price?: number;
  // Aliases
  pnl_pct?: number;
  pnl_usd?: number;
  funding_paid?: number;
  breakeven?: number;
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
  bids: { price: number; size: number }[];
  asks: { price: number; size: number }[];
  spread: number;
  mid_price: number;
}
