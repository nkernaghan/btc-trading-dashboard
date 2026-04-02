'use client';

import { useEffect } from 'react';
import { API_BASE } from '@/lib/constants';
import { useDashboardStore } from '@/stores/dashboard';

export function usePollingData() {
  const { setPrice, setSignal, setVotes, setIndicators, setPosition, setCandles, timeframe } = useDashboardStore();

  useEffect(() => {
    async function fetchAll() {
      try {
        // Fetch price
        const priceRes = await fetch(`${API_BASE}/api/price`);
        if (priceRes.ok) {
          const priceData = await priceRes.json();
          if (priceData.price) {
            setPrice(priceData.price);
          }
        }
      } catch (err) {
        console.error('[API] price fetch error:', err);
      }

      try {
        // Fetch signal + votes
        const sigRes = await fetch(`${API_BASE}/api/signal`);
        if (sigRes.ok) {
          const sigData = await sigRes.json();
          if (sigData.signal) {
            setSignal(sigData.signal);
          }
          if (sigData.votes) {
            setVotes(sigData.votes);
          }
        }
      } catch (err) {
        console.error('[API] signal fetch error:', err);
      }

      try {
        // Fetch indicators
        const indRes = await fetch(`${API_BASE}/api/indicators`);
        if (indRes.ok) {
          const indData = await indRes.json();
          setIndicators(indData);
        }
      } catch (err) {
        console.error('[API] indicators fetch error:', err);
      }

      try {
        // Fetch position
        const posRes = await fetch(`${API_BASE}/api/position/active`);
        if (posRes.ok) {
          const posData = await posRes.json();
          if (posData.position) {
            setPosition(posData.position);
          } else {
            setPosition(null);
          }
        }
      } catch (err) {
        console.error('[API] position fetch error:', err);
      }
    }

    // Fetch historical candles
    async function fetchCandles() {
      try {
        const res = await fetch(`${API_BASE}/api/candles?timeframe=${timeframe}&limit=200`);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            setCandles(data);
          }
        }
      } catch (err) {
        console.error('[API] candles fetch error:', err);
      }
    }

    fetchCandles();
    fetchAll();
    const interval = setInterval(fetchAll, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, [setPrice, setSignal, setVotes, setIndicators, setPosition, setCandles, timeframe]);
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
