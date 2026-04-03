'use client';

import { useEffect, useRef } from 'react';
import { createChart, ColorType } from 'lightweight-charts';
import type { IChartApi, ISeriesApi } from 'lightweight-charts';
import { useDashboardStore } from '@/stores/dashboard';

export default function MainChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const { candles } = useDashboardStore();

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#0c0e13' },
        textColor: '#4b5060',
        fontFamily: 'IBM Plex Mono, monospace',
        fontSize: 10,
      },
      grid: {
        vertLines: { color: 'rgba(37, 40, 56, 0.5)' },
        horzLines: { color: 'rgba(37, 40, 56, 0.5)' },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: 'rgba(74, 124, 204, 0.3)', labelBackgroundColor: '#252838' },
        horzLine: { color: 'rgba(74, 124, 204, 0.3)', labelBackgroundColor: '#252838' },
      },
      rightPriceScale: {
        borderColor: '#1e2130',
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
      timeScale: {
        borderColor: '#1e2130',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#2d9f6f',
      downColor: '#c74b4b',
      borderUpColor: '#2d9f6f',
      borderDownColor: '#c74b4b',
      wickUpColor: '#2d9f6f80',
      wickDownColor: '#c74b4b80',
    });

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    chartRef.current = chart;
    candleRef.current = candleSeries;
    volumeRef.current = volumeSeries;

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    });
    ro.observe(containerRef.current);

    return () => { ro.disconnect(); chart.remove(); };
  }, []);

  useEffect(() => {
    if (!candleRef.current || !volumeRef.current || candles.length === 0) return;
    candleRef.current.setData(candles as any);
    volumeRef.current.setData(
      candles.map(c => ({
        time: c.time,
        value: c.volume ?? 0,
        color: c.close >= c.open ? 'rgba(45,159,111,0.15)' : 'rgba(199,75,75,0.15)',
      })) as any
    );
  }, [candles]);

  return <div ref={containerRef} className="w-full h-full" />;
}
