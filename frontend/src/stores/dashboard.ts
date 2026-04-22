import { create } from 'zustand';
import { Candle, IndicatorVote, OrderBook, Position, Signal, Timeframe } from '@/lib/types';

interface DashboardStore {
  // Price data
  price: number;
  price24hChange: number;
  high24h: number;
  low24h: number;
  fundingRate: number;
  openInterest: number;
  oiDelta: number;

  // Chart data
  candles: Candle[];
  timeframe: Timeframe;

  // Signal data
  signal: Signal | null;
  votes: IndicatorVote[];
  warnings: string[];

  // Position
  position: Position | null;

  // Order book
  orderbook: OrderBook | null;

  // Indicators by category
  indicators: Record<string, IndicatorVote[]>;

  // Actions
  setPrice: (price: number) => void;
  setPrice24hChange: (change: number) => void;
  setHigh24h: (high: number) => void;
  setLow24h: (low: number) => void;
  setFundingRate: (rate: number) => void;
  setOpenInterest: (oi: number) => void;
  setOiDelta: (delta: number) => void;
  setCandles: (candles: Candle[]) => void;
  addCandle: (candle: Candle) => void;
  setTimeframe: (tf: Timeframe) => void;
  setSignal: (signal: Signal | null) => void;
  setVotes: (votes: IndicatorVote[]) => void;
  setWarnings: (warnings: string[]) => void;
  setPosition: (position: Position | null) => void;
  setOrderbook: (orderbook: OrderBook | null) => void;
  setIndicators: (indicators: Record<string, IndicatorVote[]>) => void;
}

export const useDashboardStore = create<DashboardStore>((set) => ({
  price: 0,
  price24hChange: 0,
  high24h: 0,
  low24h: 0,
  fundingRate: 0,
  openInterest: 0,
  oiDelta: 0,
  candles: [],
  timeframe: '1H',
  signal: null,
  votes: [],
  warnings: [],
  position: null,
  orderbook: null,
  indicators: {},

  setPrice: (price) => set({ price }),
  setPrice24hChange: (price24hChange) => set({ price24hChange }),
  setHigh24h: (high24h) => set({ high24h }),
  setLow24h: (low24h) => set({ low24h }),
  setFundingRate: (fundingRate) => set({ fundingRate }),
  setOpenInterest: (openInterest) => set({ openInterest }),
  setOiDelta: (oiDelta) => set({ oiDelta }),
  setCandles: (candles) => set({ candles }),
  addCandle: (candle) =>
    set((state) => {
      const existing = state.candles.findIndex((c) => c.time === candle.time);
      if (existing >= 0) {
        const updated = [...state.candles];
        updated[existing] = candle;
        return { candles: updated };
      }
      return { candles: [...state.candles, candle] };
    }),
  setTimeframe: (timeframe) => set({ timeframe }),
  setSignal: (signal) => set({ signal }),
  setVotes: (votes) => set({ votes }),
  setWarnings: (warnings) => set({ warnings }),
  setPosition: (position) => set({ position }),
  setOrderbook: (orderbook) => set({ orderbook }),
  setIndicators: (indicators) => set({ indicators }),
}));
