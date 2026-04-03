import { Timeframe } from './types';

export const API_BASE = 'http://localhost:8000';
export const WS_URL = 'ws://localhost:8000/ws';

export const COLORS = {
  long: '#26a69a',
  short: '#ef5350',
  warn: '#ff9800',
  neutral: '#5d606b',
  accent: '#2962ff',
  text: '#d1d4dc',
  textBright: '#e8eaed',
  textSecondary: '#787b86',
  textMuted: '#5d606b',
  border: '#363a45',
  borderSubtle: '#2a2e39',
  panel: '#1e222d',
  surface: '#262b3d',
  elevated: '#2a2e39',
  base: '#131722',
  btc: '#f0b90b',
};

export const CATEGORY_LABELS: Record<string, string> = {
  ORDER_FLOW: 'Order Flow',
  MACRO_DERIVATIVES: 'Macro / Derivatives',
  ON_CHAIN: 'On-Chain',
  SENTIMENT: 'Sentiment',
  TECHNICAL: 'Technical',
  VOLATILITY: 'Volatility',
};

export const VOTE_COLORS: Record<string, string> = {
  BULL: '#26a69a',
  BEAR: '#ef5350',
  NEUTRAL: '#5d606b',
  WARN: '#ff9800',
};

export const TIMEFRAMES: Timeframe[] = ['1H', '4H', '1D', '1W'];
