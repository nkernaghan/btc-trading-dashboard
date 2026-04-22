'use client';

import { useEffect, useRef } from 'react';
import { WS_URL } from '@/lib/constants';
import { useDashboardStore } from '@/stores/dashboard';

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);

  const {
    setPrice,
    setPrice24hChange,
    setHigh24h,
    setLow24h,
    addCandle,
    setOrderbook,
    setSignal,
    setVotes,
    setWarnings,
    setFundingRate,
    setOpenInterest,
    setOiDelta,
    timeframe,
  } = useDashboardStore();

  useEffect(() => {
    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WS] Connected');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const { channel, payload } = data;

          switch (channel) {
            case 'btc:trades':
              if (payload.price) setPrice(payload.price);
              if (payload.change_24h !== undefined) setPrice24hChange(payload.change_24h);
              if (payload.high_24h) setHigh24h(payload.high_24h);
              if (payload.low_24h) setLow24h(payload.low_24h);
              if (payload.funding_rate !== undefined) setFundingRate(payload.funding_rate);
              if (payload.open_interest !== undefined) setOpenInterest(payload.open_interest);
              if (payload.oi_delta !== undefined) setOiDelta(payload.oi_delta);
              break;

            case 'btc:orderbook':
              setOrderbook(payload);
              break;

            case 'btc:candle':
              // WS streams 1H candles only — skip if viewing a different timeframe
              if (timeframe === '1H') {
                addCandle({
                  time: payload.time,
                  open: payload.open,
                  high: payload.high,
                  low: payload.low,
                  close: payload.close,
                  volume: payload.volume,
                });
              }
              break;

            case 'btc:signal':
              setSignal(payload);
              if (payload.votes) setVotes(payload.votes);
              if (payload.warnings) setWarnings(payload.warnings);
              break;

            default:
              break;
          }
        } catch (err) {
          console.error('[WS] Parse error:', err);
        }
      };

      ws.onclose = () => {
        console.log('[WS] Disconnected, reconnecting in 3s...');
        reconnectTimeout.current = setTimeout(connect, 3000);
      };

      ws.onerror = (err) => {
        console.error('[WS] Error:', err);
        ws.close();
      };
    }

    connect();

    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [
    setPrice, setPrice24hChange, setHigh24h, setLow24h,
    addCandle, setOrderbook, setSignal, setVotes, setWarnings,
    setFundingRate, setOpenInterest, setOiDelta, timeframe,
  ]);
}
