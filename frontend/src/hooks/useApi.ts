'use client';

import { useEffect, useCallback } from 'react';
import { API_BASE } from '@/lib/constants';
import { useDashboardStore } from '@/stores/dashboard';

export function usePollingData() {
  const { setPrice, setIndicators, setPosition, setCandles, timeframe } = useDashboardStore();

  // Price, indicators, position poll every 5s (NOT signal — that's manual)
  useEffect(() => {
    async function fetchMarketData() {
      try {
        const priceRes = await fetch(`${API_BASE}/api/price`);
        if (priceRes.ok) {
          const priceData = await priceRes.json();
          if (priceData.price) setPrice(priceData.price);
        }
      } catch (err) {
        console.error('[API] price fetch error:', err);
      }

      try {
        const indRes = await fetch(`${API_BASE}/api/indicators`);
        if (indRes.ok) {
          const indData = await indRes.json();
          setIndicators(indData);
        }
      } catch (err) {
        console.error('[API] indicators fetch error:', err);
      }

      try {
        const posRes = await fetch(`${API_BASE}/api/position/active`);
        if (posRes.ok) {
          const posData = await posRes.json();
          setPosition(posData.position ?? null);
        }
      } catch (err) {
        console.error('[API] position fetch error:', err);
      }
    }

    async function fetchCandles() {
      try {
        const limitMap: Record<string, number> = {
          '1m': 500, '5m': 500, '15m': 500,
          '1H': 1000, '4H': 2000, '1D': 2000, '1W': 1000,
        };
        const candleLimit = limitMap[timeframe] ?? 500;
        const res = await fetch(`${API_BASE}/api/candles?timeframe=${timeframe}&limit=${candleLimit}`);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) setCandles(data);
        }
      } catch (err) {
        console.error('[API] candles fetch error:', err);
      }
    }

    fetchCandles();
    fetchMarketData();
    const interval = setInterval(fetchMarketData, 5000);
    return () => clearInterval(interval);
  }, [setPrice, setIndicators, setPosition, setCandles, timeframe]);
}

// Manual signal refresh — called by button click only
export async function fetchSignal(): Promise<boolean> {
  const { setSignal, setVotes } = useDashboardStore.getState();
  try {
    const res = await fetch(`${API_BASE}/api/signal`);
    if (res.ok) {
      const data = await res.json();
      if (data.signal) setSignal(data.signal);
      if (data.votes) setVotes(data.votes);
      return true;
    }
  } catch (err) {
    console.error('[API] signal fetch error:', err);
  }
  return false;
}

// Fetch signal history
export async function fetchSignalHistory(limit: number = 50): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE}/api/signals/history?limit=${limit}`);
    if (res.ok) return await res.json();
  } catch (err) {
    console.error('[API] signal history error:', err);
  }
  return [];
}

export async function openPosition(params: {
  direction: string;
  leverage: number;
  entry_price: number;
  size: number;
}): Promise<unknown> {
  try {
    const res = await fetch(
      `${API_BASE}/api/position/open?entry_price=${params.entry_price}&size=${params.size}&leverage=${params.leverage}&direction=${params.direction}`,
      { method: 'POST' }
    );
    if (res.ok) return await res.json();
    return null;
  } catch {
    return null;
  }
}

export async function closePosition(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/position/close`, { method: 'POST' });
    return res.ok;
  } catch {
    return false;
  }
}
