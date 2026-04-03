import { Timeframe } from './types';

export const API_BASE = 'http://localhost:8000';
export const WS_URL = 'ws://localhost:8000/ws';

export const COLORS = {
  bgPrimary: '#0a0a14',
  bgSecondary: '#12122a',
  bgTertiary: '#1a1a2e',
  textPrimary: '#e0e0e0',
  textSecondary: '#888',
  green: '#00ff88',
  red: '#ff4444',
  orange: '#ff8800',
  blue: '#4488ff',
  border: '#2a2a4a',
  btcOrange: '#f7931a',
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
  BULL: '#00ff88',
  BEAR: '#ff4444',
  NEUTRAL: '#888888',
  WARN: '#ff8800',
};

export const TIMEFRAMES: Timeframe[] = ['1H', '4H', '1D', '1W'];
