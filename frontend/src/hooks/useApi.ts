'use client';

import { useEffect } from 'react';
import { API_BASE } from '@/lib/constants';
import { useDashboardStore } from '@/stores/dashboard';
import { IndicatorVote, Position } from '@/lib/types';

export function usePollingData() {
  const { setIndicators, setPosition } = useDashboardStore();

  useEffect(() => {
    async function fetchIndicators() {
      try {
        const res = await fetch(`${API_BASE}/api/indicators`);
        if (res.ok) {
          const data: IndicatorVote[] = await res.json();
          const grouped: Record<string, IndicatorVote[]> = {};
          data.forEach((v) => {
            if (!grouped[v.category]) grouped[v.category] = [];
            grouped[v.category].push(v);
          });
          setIndicators(grouped);
        }
      } catch (err) {
        console.error('[API] indicators fetch error:', err);
      }
    }

    async function fetchPosition() {
      try {
        const res = await fetch(`${API_BASE}/api/position/active`);
        if (res.ok) {
          const data = await res.json();
          setPosition(data as Position | null);
        }
      } catch (err) {
        console.error('[API] position fetch error:', err);
      }
    }

    fetchIndicators();
    fetchPosition();

    const interval = setInterval(() => {
      fetchIndicators();
      fetchPosition();
    }, 30000);

    return () => clearInterval(interval);
  }, [setIndicators, setPosition]);
}

export async function openPosition(params: {
  direction: string;
  leverage: number;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
}): Promise<Position | null> {
  try {
    const res = await fetch(`${API_BASE}/api/position/open`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (res.ok) return await res.json();
    return null;
  } catch {
    return null;
  }
}

export async function closePosition(positionId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/position/${positionId}/close`, {
      method: 'POST',
    });
    return res.ok;
  } catch {
    return false;
  }
}
