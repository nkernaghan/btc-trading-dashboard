import { Timeframe } from './types';

export const API_BASE = 'http://localhost:8000';
export const WS_URL = 'ws://localhost:8000/ws';

export const COLORS = {
  long: '#2d9f6f',
  short: '#c74b4b',
  warn: '#c49a3c',
  neutral: '#4b5060',
  accent: '#4a7ccc',
  text: '#c8ccd4',
  textSecondary: '#6b7280',
  textMuted: '#4b5060',
  border: '#252838',
  panel: '#111318',
  surface: '#161921',
  base: '#0c0e13',
  btc: '#c49a3c',
};

export const CATEGORY_LABELS: Record<string, string> = {
  ORDER_FLOW: 'Order Flow',
  MACRO_DERIVATIVES: 'Macro',
  ON_CHAIN: 'On-Chain',
  SENTIMENT: 'Sentiment',
  TECHNICAL: 'Technical',
  VOLATILITY: 'Volatility',
};

export const VOTE_COLORS: Record<string, string> = {
  BULL: '#2d9f6f',
  BEAR: '#c74b4b',
  NEUTRAL: '#4b5060',
  WARN: '#c49a3c',
};

export const TIMEFRAMES: Timeframe[] = ['1H', '4H', '1D', '1W'];
