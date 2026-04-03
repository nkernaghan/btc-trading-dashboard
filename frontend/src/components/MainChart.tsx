'use client';

import { useEffect, useRef } from 'react';
import { createChart, ColorType, CandlestickSeries, HistogramSeries } from 'lightweight-charts';
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
        textColor: '#535868',
        fontFamily: "'IBM Plex Mono', 'SF Mono', monospace",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: 'rgba(30, 33, 48, 0.6)', style: 0 },
        horzLines: { color: 'rgba(30, 33, 48, 0.6)', style: 0 },
      },
      crosshair: {
        mode: 1,
        vertLine: {
          color: 'rgba(74, 124, 204, 0.4)',
          width: 1,
          style: 2,
          labelBackgroundColor: '#1c1f28',
        },
        horzLine: {
          color: 'rgba(74, 124, 204, 0.4)',
          width: 1,
          style: 2,
          labelBackgroundColor: '#1c1f28',
        },
      },
      rightPriceScale: {
        borderColor: '#1e2130',
        textColor: '#535868',
        scaleMargins: { top: 0.08, bottom: 0.22 },
      },
      timeScale: {
        borderColor: '#1e2130',
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

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#2d9f6f',
      downColor: '#c74b4b',
      borderUpColor: '#2d9f6f',
      borderDownColor: '#c74b4b',
      wickUpColor: 'rgba(45, 159, 111, 0.7)',
      wickDownColor: 'rgba(199, 75, 75, 0.7)',
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.86, bottom: 0 },
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

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (!candleRef.current || !volumeRef.current || candles.length === 0) return;

    candleRef.current.setData(candles as any);

    volumeRef.current.setData(
      candles.map((c) => ({
        time: c.time,
        value: c.volume ?? 0,
        color: c.close >= c.open
          ? 'rgba(45, 159, 111, 0.12)'
          : 'rgba(199, 75, 75, 0.12)',
      })) as any
    );
  }, [candles]);

  return (
    <div className="relative w-full h-full" style={{ background: '#0c0e13' }}>
      <div ref={containerRef} className="w-full h-full" />
    </div>
  );
}
