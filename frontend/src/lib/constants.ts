import { Timeframe } from './types';

export const API_BASE = 'http://localhost:8000';
export const WS_URL = 'ws://localhost:8000/ws';

export const COLORS = {
  long: '#26a69a',
  short: '#ef5350',
  warn: '#ff9800',
  neutral: '#9ca3af',
  accent: '#2962ff',
  text: '#1e1e2d',
  textBright: '#111827',
  textSecondary: '#6b7280',
  textMuted: '#9ca3af',
  border: '#e5e7eb',
  borderSubtle: '#f0f1f3',
  panel: '#f8f9fa',
  surface: '#f0f1f3',
  elevated: '#e9eaec',
  base: '#ffffff',
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
  NEUTRAL: '#9ca3af',
  WARN: '#ff9800',
};

export const TIMEFRAMES: Timeframe[] = ['1m', '5m', '15m', '1H', '4H', '1D', '1W'];
