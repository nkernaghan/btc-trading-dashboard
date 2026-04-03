'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import {
  createChart,
  ColorType,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
} from 'lightweight-charts';
import type { IChartApi, ISeriesApi } from 'lightweight-charts';
import { useDashboardStore } from '@/stores/dashboard';
import { calcEMA, calcBollingerBands, calcVWAP, calcSupportResistance } from '@/lib/indicators';
import { COLORS } from '@/lib/constants';

// ─── Bitcoin halving timestamps (UTC midnight) ─────────────────────────────
const HALVING_DATES: { time: number; label: string }[] = [
  { time: Math.floor(new Date('2012-11-28T00:00:00Z').getTime() / 1000), label: 'H1' },
  { time: Math.floor(new Date('2016-07-09T00:00:00Z').getTime() / 1000), label: 'H2' },
  { time: Math.floor(new Date('2020-05-11T00:00:00Z').getTime() / 1000), label: 'H3' },
  { time: Math.floor(new Date('2024-04-20T00:00:00Z').getTime() / 1000), label: 'H4' },
  { time: Math.floor(new Date('2028-04-15T00:00:00Z').getTime() / 1000), label: 'H5' },
  { time: Math.floor(new Date('2032-04-14T00:00:00Z').getTime() / 1000), label: 'H6' },
  { time: Math.floor(new Date('2036-04-13T00:00:00Z').getTime() / 1000), label: 'H7' },
];

const SECONDS_PER_DAY = 86400;

// 4-year cycle: bull phase starts ~6 months after halving, bear ~6 months before next
// expressed as offsets in seconds
const BULL_START_OFFSET = 180 * SECONDS_PER_DAY;  // +6 months after halving
const BULL_END_OFFSET   = 540 * SECONDS_PER_DAY;  // +18 months after halving

// Zone phase offsets (seconds after halving)
// Accumulation: 0 – 6 months, Bull: 6 – 18 months, Distribution: 18 – 24 months, Bear: 24 months – next halving
const ZONE_ACCUM_END  =  180 * SECONDS_PER_DAY; //  6 months
const ZONE_BULL_END   =  540 * SECONDS_PER_DAY; // 18 months
const ZONE_DIST_END   =  730 * SECONDS_PER_DAY; // ~24 months

// Zone line colors (horizontal dashed lines at chart top)
const ZONE_COLORS = {
  accum: 'rgba(59, 130, 246, 0.65)',   // blue  — accumulation
  bull:  'rgba(34, 197, 94, 0.65)',    // green — bull run
  dist:  'rgba(249, 115, 22, 0.65)',   // orange — distribution
  bear:  'rgba(239, 68, 68, 0.65)',    // red   — bear market
} as const;

// Number of S/R levels to show per side
const SR_TOP_N = 5;

// ─── Indicator toggle state ────────────────────────────────────────────────
interface IndicatorState {
  ema21: boolean;
  ema55: boolean;
  ema200: boolean;
  bb: boolean;
  vwap: boolean;
  halving: boolean;
  cycle4y: boolean;
  zones: boolean;
  sr: boolean;
}

const DEFAULT_INDICATORS: IndicatorState = {
  ema21: true,
  ema55: true,
  ema200: true,
  bb: false,
  vwap: false,
  halving: false,
  cycle4y: false,
  zones: false,
  sr: false,
};

type IndicatorKey = keyof IndicatorState;

const INDICATOR_BUTTONS: { key: IndicatorKey; label: string }[] = [
  { key: 'ema21',   label: 'EMA 21'  },
  { key: 'ema55',   label: 'EMA 55'  },
  { key: 'ema200',  label: 'EMA 200' },
  { key: 'bb',      label: 'BB'      },
  { key: 'vwap',    label: 'VWAP'    },
  { key: 'halving', label: 'Halving' },
  { key: 'cycle4y', label: '4Y Cycle'},
  { key: 'zones',   label: 'Zones'   },
  { key: 'sr',      label: 'S/R'     },
];

// ─── Colours for each series ───────────────────────────────────────────────
const EMA_COLORS: Record<string, string> = {
  ema21:  '#2962ff',
  ema55:  '#ff9800',
  ema200: '#ef5350',
};

export default function MainChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef     = useRef<IChartApi | null>(null);

  // Main series
  const candleRef  = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeRef  = useRef<ISeriesApi<'Histogram'>   | null>(null);

  // Overlay series
  const ema21Ref   = useRef<ISeriesApi<'Line'> | null>(null);
  const ema55Ref   = useRef<ISeriesApi<'Line'> | null>(null);
  const ema200Ref  = useRef<ISeriesApi<'Line'> | null>(null);
  const bbUpperRef = useRef<ISeriesApi<'Line'> | null>(null);
  const bbMidRef   = useRef<ISeriesApi<'Line'> | null>(null);
  const bbLowerRef = useRef<ISeriesApi<'Line'> | null>(null);
  const vwapRef    = useRef<ISeriesApi<'Line'> | null>(null);

  // Halving vertical-line series (one dummy LineSeries per halving drawn as a
  // very narrow range so it looks like a vertical line)
  const halvingSeriesRefs = useRef<ISeriesApi<'Line'>[]>([]);

  // 4Y cycle background series (pairs of area lines)
  const cycleSeriesRefs = useRef<ISeriesApi<'Line'>[]>([]);

  // Zone phase series — 4 colored dashed lines per cycle (accum/bull/dist/bear)
  // Indexed as [cycleIdx * 4 + phaseIdx]
  const zoneSeriesRefs = useRef<ISeriesApi<'Line'>[]>([]);

  // S/R level series — [0..SR_TOP_N-1] resistance, [SR_TOP_N..2*SR_TOP_N-1] support
  const srSeriesRefs = useRef<ISeriesApi<'Line'>[]>([]);

  const [indicators, setIndicators] = useState<IndicatorState>(DEFAULT_INDICATORS);

  const { candles } = useDashboardStore();

  // ─── Chart initialisation ────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#ffffff' },
        textColor: '#6b7280',
        fontFamily: "'Inter', sans-serif",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(229, 231, 235, 0.8)', style: 0 },
        horzLines: { color: 'rgba(229, 231, 235, 0.8)', style: 0 },
      },
      crosshair: {
        mode: 1,
        vertLine: {
          color: 'rgba(41, 98, 255, 0.4)',
          width: 1,
          style: 2,
          labelBackgroundColor: '#e9eaec',
        },
        horzLine: {
          color: 'rgba(41, 98, 255, 0.4)',
          width: 1,
          style: 2,
          labelBackgroundColor: '#e9eaec',
        },
      },
      rightPriceScale: {
        borderColor: '#e5e7eb',
        textColor: '#6b7280',
        scaleMargins: { top: 0.08, bottom: 0.22 },
      },
      timeScale: {
        borderColor: '#e5e7eb',
        timeVisible: true,
        secondsVisible: false,
        fixLeftEdge: false,
        fixRightEdge: false,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
    });

    // Candles
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor:       '#26a69a',
      downColor:     '#ef5350',
      borderUpColor: '#26a69a',
      borderDownColor: '#ef5350',
      wickUpColor:   'rgba(38, 166, 154, 0.7)',
      wickDownColor: 'rgba(239, 83, 80, 0.7)',
    });

    // Volume
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.86, bottom: 0 },
    });

    // EMA 21
    const ema21Series = chart.addSeries(LineSeries, {
      color:       EMA_COLORS.ema21,
      lineWidth:   1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      visible: DEFAULT_INDICATORS.ema21,
    });

    // EMA 55
    const ema55Series = chart.addSeries(LineSeries, {
      color:       EMA_COLORS.ema55,
      lineWidth:   1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      visible: DEFAULT_INDICATORS.ema55,
    });

    // EMA 200
    const ema200Series = chart.addSeries(LineSeries, {
      color:       EMA_COLORS.ema200,
      lineWidth:   1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      visible: DEFAULT_INDICATORS.ema200,
    });

    // Bollinger upper
    const bbUpperSeries = chart.addSeries(LineSeries, {
      color:       'rgba(41, 98, 255, 0.5)',
      lineWidth:   1,
      lineStyle:   2, // dashed
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      visible: DEFAULT_INDICATORS.bb,
    });

    // Bollinger middle (SMA)
    const bbMidSeries = chart.addSeries(LineSeries, {
      color:       'rgba(41, 98, 255, 0.4)',
      lineWidth:   1,
      lineStyle:   1, // dotted
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      visible: DEFAULT_INDICATORS.bb,
    });

    // Bollinger lower
    const bbLowerSeries = chart.addSeries(LineSeries, {
      color:       'rgba(41, 98, 255, 0.5)',
      lineWidth:   1,
      lineStyle:   2, // dashed
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      visible: DEFAULT_INDICATORS.bb,
    });

    // VWAP
    const vwapSeries = chart.addSeries(LineSeries, {
      color:       '#9c27b0',
      lineWidth:   1,
      lineStyle:   2, // dashed
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      visible: DEFAULT_INDICATORS.vwap,
    });

    // Halving marker series — one per halving, shows as a colored dot on the chart
    const hSeriesArr: ISeriesApi<'Line'>[] = [];
    for (const hv of HALVING_DATES) {
      const hvSeries = chart.addSeries(LineSeries, {
        color: '#7c3aed',
        lineWidth: 2,
        pointMarkersVisible: true,
        pointMarkersRadius: 5,
        priceScaleId: '',  // overlay — doesn't affect Y-axis
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerVisible: true,
        visible: DEFAULT_INDICATORS.halving,
        title: hv.label,
      } as any);
      hSeriesArr.push(hvSeries);
    }

    // 4Y cycle background shading — two LineSeries (upper / lower boundary)
    // per bull phase rendered as a shaded area via repeated baseline approach.
    const cSeriesArr: ISeriesApi<'Line'>[] = [];
    for (let i = 0; i < HALVING_DATES.length - 1; i++) {
      // Use lineWidth: 1 with fully transparent color so no actual line is
      // rendered — the visual shading comes from the series fill logic below.
      const bullUpper = chart.addSeries(LineSeries, {
        color:       'rgba(38, 166, 154, 0.25)',
        lineWidth:   1,
        lineStyle:   2,
        priceScaleId: '',
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
        visible: DEFAULT_INDICATORS.cycle4y,
      });
      const bullLower = chart.addSeries(LineSeries, {
        color:       'rgba(239, 83, 80, 0.25)',
        lineWidth:   1,
        lineStyle:   2,
        priceScaleId: '',
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
        visible: DEFAULT_INDICATORS.cycle4y,
      });
      cSeriesArr.push(bullUpper, bullLower);
    }

    // Zone phase series — 4 horizontal dashed lines (at chart top) per cycle.
    // Each line spans the phase's time range and is color-coded by phase.
    // Order per cycle: [accum, bull, dist, bear]
    const zSeriesArr: ISeriesApi<'Line'>[] = [];
    const zonePhaseColors = [
      ZONE_COLORS.accum,
      ZONE_COLORS.bull,
      ZONE_COLORS.dist,
      ZONE_COLORS.bear,
    ];
    for (let i = 0; i < HALVING_DATES.length - 1; i++) {
      for (const phaseColor of zonePhaseColors) {
        const phaseSeries = chart.addSeries(LineSeries, {
          color:       phaseColor,
          lineWidth:   3,
          lineStyle:   2, // dashed
          priceScaleId: '',  // overlay — doesn't affect Y-axis scaling
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
          visible: DEFAULT_INDICATORS.zones,
        });
        zSeriesArr.push(phaseSeries);
      }
    }

    // S/R level series — SR_TOP_N resistance (red dashed) + SR_TOP_N support (green dashed)
    const srArr: ISeriesApi<'Line'>[] = [];
    for (let i = 0; i < SR_TOP_N; i++) {
      srArr.push(chart.addSeries(LineSeries, {
        color:       'rgba(239, 68, 68, 0.8)',
        lineWidth:   1,
        lineStyle:   2,
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerVisible: false,
        visible: DEFAULT_INDICATORS.sr,
      }));
    }
    for (let i = 0; i < SR_TOP_N; i++) {
      srArr.push(chart.addSeries(LineSeries, {
        color:       'rgba(34, 197, 94, 0.8)',
        lineWidth:   1,
        lineStyle:   2,
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerVisible: false,
        visible: DEFAULT_INDICATORS.sr,
      }));
    }

    chartRef.current       = chart;
    candleRef.current      = candleSeries;
    volumeRef.current      = volumeSeries;
    ema21Ref.current       = ema21Series;
    ema55Ref.current       = ema55Series;
    ema200Ref.current      = ema200Series;
    bbUpperRef.current     = bbUpperSeries;
    bbMidRef.current       = bbMidSeries;
    bbLowerRef.current     = bbLowerSeries;
    vwapRef.current        = vwapSeries;
    halvingSeriesRefs.current = hSeriesArr;
    cycleSeriesRefs.current   = cSeriesArr;
    zoneSeriesRefs.current    = zSeriesArr;
    srSeriesRefs.current      = srArr;

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({
          width:  containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, []);

  // ─── Populate series whenever candle data changes ────────────────────────
  useEffect(() => {
    if (
      !candleRef.current ||
      !volumeRef.current ||
      candles.length === 0
    ) return;

    // Deduplicate and sort candles by time (lightweight-charts requires strictly ascending)
    const seen = new Set<number>();
    const dedupedCandles = candles
      .filter((c) => {
        if (seen.has(c.time)) return false;
        seen.add(c.time);
        return true;
      })
      .sort((a, b) => a.time - b.time);

    candleRef.current.setData(dedupedCandles as any);
    volumeRef.current.setData(
      dedupedCandles.map((c) => ({
        time:  c.time,
        value: c.volume ?? 0,
        color: c.close >= c.open
          ? 'rgba(38, 166, 154, 0.18)'
          : 'rgba(239, 83, 80, 0.18)',
      })) as any
    );

    const closes = dedupedCandles.map((c) => c.close);
    const times  = dedupedCandles.map((c) => c.time);

    // Helper: map parallel value array to [{time, value}] skipping NaN
    const toSeries = (values: number[]) =>
      values
        .map((v, i) => ({ time: times[i] as any, value: v }))
        .filter((p) => !isNaN(p.value));

    // EMAs
    if (ema21Ref.current)  ema21Ref.current.setData(toSeries(calcEMA(closes, 21)));
    if (ema55Ref.current)  ema55Ref.current.setData(toSeries(calcEMA(closes, 55)));
    if (ema200Ref.current) ema200Ref.current.setData(toSeries(calcEMA(closes, 200)));

    // Bollinger Bands
    const bb = calcBollingerBands(closes, 20, 2);
    if (bbUpperRef.current) bbUpperRef.current.setData(toSeries(bb.upper));
    if (bbMidRef.current)   bbMidRef.current.setData(toSeries(bb.middle));
    if (bbLowerRef.current) bbLowerRef.current.setData(toSeries(bb.lower));

    // VWAP
    if (vwapRef.current) {
      vwapRef.current.setData(toSeries(calcVWAP(dedupedCandles)));
    }

    // Halving lines — place two data points bracketing each halving date
    // at the historical high/low of the dataset so the line spans the chart.
    const priceMin = Math.min(...dedupedCandles.map((c) => c.low));
    const priceMax = Math.max(...dedupedCandles.map((c) => c.high));
    const firstTime = times[0];
    const lastTime  = times[times.length - 1];

    // Only show halvings that fall within the candle data range
    // (no future projections — they stretch the time axis)
    HALVING_DATES.forEach((hv, idx) => {
      const series = halvingSeriesRefs.current[idx];
      if (!series) return;

      const t = hv.time;

      // Only show if within candle range
      if (t < firstTime - SECONDS_PER_DAY * 30 || t > lastTime + SECONDS_PER_DAY * 30) {
        series.setData([]);
        return;
      }

      // Find closest candle
      let closestIdx = 0;
      let minDist = Infinity;
      for (let i = 0; i < times.length; i++) {
        if (Math.abs(times[i] - t) < minDist) {
          minDist = Math.abs(times[i] - t);
          closestIdx = i;
        }
      }

      series.setData([{ time: times[closestIdx] as any, value: dedupedCandles[closestIdx]?.close ?? 0 }]);
    });

    // 4Y Cycle shading — draw upper/lower boundary lines for each bull phase.
    // For cycles that extend beyond the last candle we generate synthetic
    // timestamps at daily resolution so the lines appear in the future.
    for (let i = 0; i < HALVING_DATES.length - 1; i++) {
      const bullStart = HALVING_DATES[i].time + BULL_START_OFFSET;
      const bullEnd   = HALVING_DATES[i].time + BULL_END_OFFSET;

      const upperSeries = cycleSeriesRefs.current[i * 2];
      const lowerSeries = cycleSeriesRefs.current[i * 2 + 1];
      if (!upperSeries || !lowerSeries) continue;

      // Build the time range for this phase (candle data where available,
      // synthetic daily ticks for the future portion)
      const phaseCandles = dedupedCandles.filter(
        (c) => c.time >= bullStart && c.time <= bullEnd
      );

      // Only use actual candle data — no synthetic future points
      const allPhasePoints = phaseCandles.map((c) => ({ time: c.time, high: c.high, low: c.low }));

      if (allPhasePoints.length === 0) {
        upperSeries.setData([]);
        lowerSeries.setData([]);
        continue;
      }

      upperSeries.setData(
        allPhasePoints.map((p) => ({ time: p.time as any, value: p.high }))
      );
      lowerSeries.setData(
        allPhasePoints.map((p) => ({ time: p.time as any, value: p.low }))
      );
    }

    // ── Zone phase shading ───────────────────────────────────────────────────
    // Draw 4 colored horizontal dashed lines at priceMax per cycle phase.
    // The line sits at the top of the chart and acts as a phase label band.
    // Each cycle has 4 phases: accum (0–6m), bull (6–18m), dist (18–24m), bear (24m–next halving).
    for (let i = 0; i < HALVING_DATES.length - 1; i++) {
      const halvingTime    = HALVING_DATES[i].time;
      const nextHalving    = HALVING_DATES[i + 1].time;

      const phases = [
        { start: halvingTime,                          end: halvingTime + ZONE_ACCUM_END  },
        { start: halvingTime + ZONE_ACCUM_END,         end: halvingTime + ZONE_BULL_END   },
        { start: halvingTime + ZONE_BULL_END,          end: halvingTime + ZONE_DIST_END   },
        { start: halvingTime + ZONE_DIST_END,          end: nextHalving                   },
      ];

      phases.forEach((phase, phaseIdx) => {
        const zSeries = zoneSeriesRefs.current[i * 4 + phaseIdx];
        if (!zSeries) return;

        // Generate a two-point horizontal line at priceMax for this phase.
        // We always render even for future phases — lightweight-charts accepts
        // any ascending timestamps including future ones.
        const startT = Math.max(phase.start, firstTime - SECONDS_PER_DAY);
        const endT   = Math.min(phase.end, lastTime + SECONDS_PER_DAY);

        if (startT >= endT) {
          zSeries.setData([]);
          return;
        }

        // Two anchor points are sufficient for a straight horizontal line
        zSeries.setData([
          { time: startT as any, value: priceMax },
          { time: endT   as any, value: priceMax },
        ]);
      });
    }

    // ── Support / Resistance levels ──────────────────────────────────────────
    const sr = calcSupportResistance(dedupedCandles, 20, 0.01, SR_TOP_N);

    // Each level becomes a horizontal line spanning the full candle range
    sr.resistance.forEach((price, idx) => {
      const s = srSeriesRefs.current[idx];
      if (!s) return;
      s.setData([
        { time: firstTime as any, value: price },
        { time: lastTime  as any, value: price },
      ]);
    });
    // Clear any unused resistance slots
    for (let i = sr.resistance.length; i < SR_TOP_N; i++) {
      srSeriesRefs.current[i]?.setData([]);
    }

    sr.support.forEach((price, idx) => {
      const s = srSeriesRefs.current[SR_TOP_N + idx];
      if (!s) return;
      s.setData([
        { time: firstTime as any, value: price },
        { time: lastTime  as any, value: price },
      ]);
    });
    // Clear any unused support slots
    for (let i = sr.support.length; i < SR_TOP_N; i++) {
      srSeriesRefs.current[SR_TOP_N + i]?.setData([]);
    }
  }, [candles, indicators.halving]);

  // ─── Sync series visibility when toggles change ──────────────────────────
  useEffect(() => {
    ema21Ref.current?.applyOptions({ visible: indicators.ema21 });
    ema55Ref.current?.applyOptions({ visible: indicators.ema55 });
    ema200Ref.current?.applyOptions({ visible: indicators.ema200 });

    bbUpperRef.current?.applyOptions({ visible: indicators.bb });
    bbMidRef.current?.applyOptions({ visible: indicators.bb });
    bbLowerRef.current?.applyOptions({ visible: indicators.bb });

    vwapRef.current?.applyOptions({ visible: indicators.vwap });

    halvingSeriesRefs.current.forEach((s) => {
      if (s) s.applyOptions({ visible: indicators.halving });
    });

    cycleSeriesRefs.current.forEach((s) =>
      s.applyOptions({ visible: indicators.cycle4y })
    );

    zoneSeriesRefs.current.forEach((s) =>
      s.applyOptions({ visible: indicators.zones })
    );

    srSeriesRefs.current.forEach((s) =>
      s.applyOptions({ visible: indicators.sr })
    );
  }, [indicators]);

  // ─── Toggle handler ──────────────────────────────────────────────────────
  const toggle = useCallback((key: IndicatorKey) => {
    setIndicators((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  // ─── Toolbar button colours ──────────────────────────────────────────────
  const buttonColor = (key: IndicatorKey): string => {
    const colorMap: Partial<Record<IndicatorKey, string>> = {
      ema21:   EMA_COLORS.ema21,
      ema55:   EMA_COLORS.ema55,
      ema200:  EMA_COLORS.ema200,
      bb:      '#2962ff',
      vwap:    '#9c27b0',
      halving: '#7c3aed',
      cycle4y: '#26a69a',
      zones:   '#f97316',
      sr:      '#22c55e',
    };
    return colorMap[key] ?? COLORS.accent;
  };

  return (
    <div className="relative w-full h-full" style={{ background: '#ffffff' }}>
      {/* ── Indicator toggle toolbar ─────────────────────────────────── */}
      <div
        style={{
          position:   'absolute',
          top:        8,
          left:       8,
          zIndex:     10,
          display:    'flex',
          gap:        4,
          flexWrap:   'wrap',
          maxWidth:   'calc(100% - 80px)',
        }}
      >
        {INDICATOR_BUTTONS.map(({ key, label }) => {
          const active = indicators[key];
          const color  = buttonColor(key);
          return (
            <button
              key={key}
              onClick={() => toggle(key)}
              title={label}
              style={{
                height:          20,
                padding:         '0 7px',
                fontSize:        10,
                fontFamily:      'Inter, sans-serif',
                fontWeight:      500,
                letterSpacing:   '0.03em',
                borderRadius:    4,
                border:          `1px solid ${active ? color : 'rgba(229,231,235,0.9)'}`,
                background:      active ? `${color}18` : 'rgba(255,255,255,0.85)',
                color:           active ? color : '#9ca3af',
                cursor:          'pointer',
                transition:      'all 0.12s ease',
                lineHeight:      '18px',
                backdropFilter:  'blur(4px)',
                whiteSpace:      'nowrap',
              }}
            >
              {label}
            </button>
          );
        })}
      </div>

      {/* ── Chart container ──────────────────────────────────────────── */}
      <div ref={containerRef} className="w-full h-full" />
    </div>
  );
}
