/**
 * Pure TypeScript indicator calculation functions.
 * No React or charting library dependencies.
 */

/**
 * Calculates an Exponential Moving Average for a series of closing prices.
 * Returns an array of the same length — leading values before the period
 * is met are filled with NaN so the chart series can skip them cleanly.
 */
export function calcEMA(closes: number[], period: number): number[] {
  const result: number[] = new Array(closes.length).fill(NaN);
  if (closes.length < period) return result;

  const multiplier = 2 / (period + 1);

  // Seed with a simple average of the first `period` values
  let ema =
    closes.slice(0, period).reduce((sum, v) => sum + v, 0) / period;
  result[period - 1] = ema;

  for (let i = period; i < closes.length; i++) {
    ema = (closes[i] - ema) * multiplier + ema;
    result[i] = ema;
  }

  return result;
}

/**
 * Calculates Bollinger Bands (Simple MA ± k standard deviations).
 * Returns upper, middle, and lower arrays of the same length as `closes`.
 * Values before the first full window are NaN.
 */
export function calcBollingerBands(
  closes: number[],
  period: number = 20,
  stdDevMultiplier: number = 2
): { upper: number[]; middle: number[]; lower: number[] } {
  const len = closes.length;
  const upper: number[] = new Array(len).fill(NaN);
  const middle: number[] = new Array(len).fill(NaN);
  const lower: number[] = new Array(len).fill(NaN);

  for (let i = period - 1; i < len; i++) {
    const slice = closes.slice(i - period + 1, i + 1);
    const sma = slice.reduce((s, v) => s + v, 0) / period;
    const variance =
      slice.reduce((s, v) => s + (v - sma) ** 2, 0) / period;
    const sd = Math.sqrt(variance);

    middle[i] = sma;
    upper[i] = sma + stdDevMultiplier * sd;
    lower[i] = sma - stdDevMultiplier * sd;
  }

  return { upper, middle, lower };
}

/**
 * Calculates the Volume Weighted Average Price (VWAP).
 * Uses the typical price (high + low + close) / 3 as the price basis.
 * Resets at the start of the dataset — for intraday anchoring, pass only
 * the candles for the current session.
 */
export function calcVWAP(
  candles: { high: number; low: number; close: number; volume: number }[]
): number[] {
  const result: number[] = new Array(candles.length).fill(NaN);
  let cumulativeTpv = 0; // sum of (typical price × volume)
  let cumulativeVolume = 0;

  for (let i = 0; i < candles.length; i++) {
    const { high, low, close, volume } = candles[i];
    const typicalPrice = (high + low + close) / 3;
    cumulativeTpv += typicalPrice * volume;
    cumulativeVolume += volume;
    result[i] = cumulativeVolume > 0 ? cumulativeTpv / cumulativeVolume : NaN;
  }

  return result;
}

/**
 * Builds a volume profile from candle data.
 * Bins all candle volumes into `levels` price buckets and returns
 * the bucket boundaries plus the aggregated volume for each bucket.
 */
export interface VolumeProfileBucket {
  priceLow: number;
  priceHigh: number;
  priceMid: number;
  volume: number;
  isPoc: boolean; // Point of Control — highest volume bucket
}

export function calcVolumeProfile(
  candles: { high: number; low: number; close: number; volume: number }[],
  levels: number = 20
): VolumeProfileBucket[] {
  if (candles.length === 0) return [];

  const priceMin = Math.min(...candles.map((c) => c.low));
  const priceMax = Math.max(...candles.map((c) => c.high));
  const range = priceMax - priceMin;
  if (range === 0) return [];

  const bucketSize = range / levels;
  const buckets: number[] = new Array(levels).fill(0);

  for (const candle of candles) {
    // Distribute candle volume evenly across all buckets the candle spans
    const startBucket = Math.floor((candle.low - priceMin) / bucketSize);
    const endBucket = Math.min(
      Math.floor((candle.high - priceMin) / bucketSize),
      levels - 1
    );
    const spannedBuckets = endBucket - startBucket + 1;
    const volumePerBucket = candle.volume / spannedBuckets;

    for (let b = startBucket; b <= endBucket; b++) {
      if (b >= 0 && b < levels) {
        buckets[b] += volumePerBucket;
      }
    }
  }

  const maxVolume = Math.max(...buckets);
  const pocIndex = buckets.indexOf(maxVolume);

  return buckets.map((vol, i) => ({
    priceLow: priceMin + i * bucketSize,
    priceHigh: priceMin + (i + 1) * bucketSize,
    priceMid: priceMin + (i + 0.5) * bucketSize,
    volume: vol,
    isPoc: i === pocIndex,
  }));
}

/**
 * Calculates support and resistance levels from candle data by finding swing
 * highs and swing lows over a rolling lookback window, then grouping nearby
 * levels within a tolerance band and ranking by touch count.
 *
 * Returns the top `topN` support levels (below current price) and top `topN`
 * resistance levels (above current price), sorted by strength descending.
 */
export interface SRLevel {
  price: number;
  touches: number;
  type: 'support' | 'resistance';
}

export function calcSupportResistance(
  candles: { time: number; high: number; low: number; close: number }[],
  lookback: number = 20,
  tolerance: number = 0.01,
  topN: number = 5
): { support: number[]; resistance: number[] } {
  if (candles.length < lookback * 2 + 1) {
    return { support: [], resistance: [] };
  }

  const swingHighs: number[] = [];
  const swingLows: number[] = [];

  // Identify swing highs and lows: a candle is a swing high if its high is the
  // highest in the window [i-lookback, i+lookback], and a swing low if its low
  // is the lowest in that same window.
  for (let i = lookback; i < candles.length - lookback; i++) {
    const windowHighs = candles.slice(i - lookback, i + lookback + 1).map((c) => c.high);
    const windowLows  = candles.slice(i - lookback, i + lookback + 1).map((c) => c.low);
    const maxHigh = Math.max(...windowHighs);
    const minLow  = Math.min(...windowLows);

    if (candles[i].high === maxHigh) swingHighs.push(candles[i].high);
    if (candles[i].low  === minLow)  swingLows.push(candles[i].low);
  }

  // Group nearby price levels within the tolerance band by clustering
  function clusterLevels(prices: number[]): { price: number; touches: number }[] {
    if (prices.length === 0) return [];
    const sorted = [...prices].sort((a, b) => a - b);
    const clusters: { price: number; touches: number }[] = [];

    let groupStart = 0;
    for (let i = 1; i <= sorted.length; i++) {
      const isLast = i === sorted.length;
      const outsideTolerance = !isLast && sorted[i] > sorted[groupStart] * (1 + tolerance);
      if (isLast || outsideTolerance) {
        const group = sorted.slice(groupStart, i);
        const avgPrice = group.reduce((s, v) => s + v, 0) / group.length;
        clusters.push({ price: avgPrice, touches: group.length });
        groupStart = i;
      }
    }

    return clusters.sort((a, b) => b.touches - a.touches);
  }

  const resistanceClusters = clusterLevels(swingHighs);
  const supportClusters    = clusterLevels(swingLows);

  return {
    resistance: resistanceClusters.slice(0, topN).map((c) => c.price),
    support:    supportClusters.slice(0, topN).map((c) => c.price),
  };
}

/**
 * Calculates estimated liquidation prices for long and short positions
 * at various leverage levels relative to an entry price.
 *
 * Formula (simplified, no maintenance margin):
 *   Long  liquidation = entry × (1 − 1/leverage)
 *   Short liquidation = entry × (1 + 1/leverage)
 */
export interface LiquidationLevel {
  leverage: number;
  longLiq: number;
  shortLiq: number;
  longDistancePct: number;
  shortDistancePct: number;
}

export function calcLiquidationLevels(
  currentPrice: number,
  leverages: number[] = [5, 10, 20, 25, 30, 40]
): LiquidationLevel[] {
  return leverages.map((lev) => {
    const longLiq = currentPrice * (1 - 1 / lev);
    const shortLiq = currentPrice * (1 + 1 / lev);
    return {
      leverage: lev,
      longLiq,
      shortLiq,
      longDistancePct: ((currentPrice - longLiq) / currentPrice) * 100,
      shortDistancePct: ((shortLiq - currentPrice) / currentPrice) * 100,
    };
  });
}
