'use client';

import { useState } from 'react';
import { useDashboardStore } from '@/stores/dashboard';
import { formatFunding, formatCompact, formatPct } from '@/lib/format';
import { COLORS } from '@/lib/constants';

const TABS = ['Macro', 'Sentiment', 'Funding', 'OI', 'News'] as const;
type Tab = typeof TABS[number];

const MACRO_LABELS: Record<string, string> = {
  DXY: 'DXY',
  SPX: 'SPX',
  NQ: 'NQ',
  US10Y: 'US10Y',
  GOLD: 'Gold',
  BTC_DOM: 'BTC.D',
};

function MacroCell({ label, price, changePct }: { label: string; price: number; changePct: number }) {
  const positive = changePct >= 0;
  const changeColor = positive ? COLORS.long : COLORS.short;

  return (
    <div
      className="flex flex-col justify-center px-3 py-1 flex-shrink-0"
      style={{ borderRight: `1px solid ${COLORS.border}` }}
    >
      <div className="panel-label mb-0.5" style={{ fontSize: 8 }}>
        {MACRO_LABELS[label] || label}
      </div>
      <div
        className="data-value font-semibold"
        style={{ color: COLORS.text, fontSize: 12, lineHeight: 1.2 }}
      >
        {price?.toLocaleString(undefined, { maximumFractionDigits: 2 }) ?? '--'}
      </div>
      <div
        className="data-value text-[9px] font-medium"
        style={{ color: changeColor }}
      >
        {positive ? '+' : ''}{formatPct(changePct)}
      </div>
    </div>
  );
}

function FearGreedArc({ value }: { value: number }) {
  const color =
    value <= 25 ? COLORS.short
    : value <= 45 ? '#c47c3c'
    : value <= 55 ? COLORS.warn
    : value <= 75 ? '#6f9f2d'
    : COLORS.long;

  const label =
    value <= 25 ? 'Extreme Fear'
    : value <= 45 ? 'Fear'
    : value <= 55 ? 'Neutral'
    : value <= 75 ? 'Greed'
    : 'Extreme Greed';

  return (
    <div className="flex flex-col items-center justify-center px-4">
      <div className="panel-label mb-1" style={{ fontSize: 8 }}>FEAR & GREED</div>
      <div
        className="data-value font-bold"
        style={{ fontSize: 28, color, lineHeight: 1, textShadow: `0 0 16px ${color}40` }}
      >
        {value}
      </div>
      <div
        className="text-[9px] font-medium mt-0.5"
        style={{ color, fontFamily: 'IBM Plex Sans, sans-serif', letterSpacing: '0.05em' }}
      >
        {label}
      </div>
      {/* Mini bar */}
      <div
        className="mt-2 rounded-full overflow-hidden"
        style={{ width: 80, height: 3, background: COLORS.border }}
      >
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${value}%`, background: color }}
        />
      </div>
    </div>
  );
}

export default function BottomCharts() {
  const [activeTab, setActiveTab] = useState<Tab>('Macro');
  const { fundingRate, openInterest, oiDelta, indicators } = useDashboardStore();

  const macro = (indicators as any)?.macro_data as Record<string, { price: number; change_pct: number }> | undefined;
  const fearGreed = (indicators as any)?.sentiment_fear_greed as { value: number; classification: string } | undefined;
  const dominance = (indicators as any)?.sentiment_btc_dominance as { btc_dominance: number } | undefined;
  const news = (indicators as any)?.news_articles as { title: string; source: string; url?: string }[] | undefined;

  const fundingColor =
    Math.abs(fundingRate ?? 0) > 0.001
      ? COLORS.warn
      : (fundingRate ?? 0) >= 0
      ? COLORS.long
      : COLORS.short;

  return (
    <div
      className="flex flex-col h-full"
      style={{ background: COLORS.panel }}
    >
      {/* Tab bar */}
      <div
        className="flex items-center flex-shrink-0"
        style={{ borderBottom: `1px solid ${COLORS.border}`, height: 28 }}
      >
        {TABS.map((tab) => {
          const active = activeTab === tab;
          return (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className="relative px-3 h-full text-[10px] font-medium transition-colors duration-100"
              style={{
                color: active ? COLORS.accent : COLORS.textMuted,
                background: active ? 'rgba(74,124,204,0.06)' : 'transparent',
                fontFamily: 'IBM Plex Sans, sans-serif',
                letterSpacing: '0.04em',
                borderRight: `1px solid ${COLORS.border}`,
              }}
            >
              {tab}
              {active && (
                <div
                  style={{
                    position: 'absolute',
                    bottom: 0,
                    left: 0,
                    right: 0,
                    height: 1,
                    background: COLORS.accent,
                  }}
                />
              )}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">

        {/* ── Macro ─────────────────────────────── */}
        {activeTab === 'Macro' && (
          <div className="flex items-stretch h-full overflow-x-auto">
            {macro ? (
              Object.entries(macro).map(([key, data]) => (
                <MacroCell
                  key={key}
                  label={key}
                  price={data.price}
                  changePct={data.change_pct}
                />
              ))
            ) : (
              <div className="flex items-center px-4 text-[10px]" style={{ color: COLORS.textMuted }}>
                Loading market data...
              </div>
            )}
            {dominance && (
              <div
                className="flex flex-col justify-center px-3 flex-shrink-0"
                style={{ borderRight: `1px solid ${COLORS.border}` }}
              >
                <div className="panel-label mb-0.5" style={{ fontSize: 8 }}>BTC.D</div>
                <div
                  className="data-value font-semibold"
                  style={{ color: COLORS.btc, fontSize: 12 }}
                >
                  {dominance.btc_dominance}%
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Sentiment ──────────────────────────── */}
        {activeTab === 'Sentiment' && (
          <div className="flex items-stretch h-full">
            {fearGreed ? (
              <FearGreedArc value={fearGreed.value} />
            ) : (
              <div className="flex items-center px-4 text-[10px]" style={{ color: COLORS.textMuted }}>
                Loading...
              </div>
            )}
            {dominance && (
              <div
                className="flex flex-col items-center justify-center px-5"
                style={{ borderLeft: `1px solid ${COLORS.border}` }}
              >
                <div className="panel-label mb-1" style={{ fontSize: 8 }}>BTC DOMINANCE</div>
                <div
                  className="data-value font-bold"
                  style={{ fontSize: 22, color: COLORS.btc, lineHeight: 1 }}
                >
                  {dominance.btc_dominance}%
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Funding ────────────────────────────── */}
        {activeTab === 'Funding' && (
          <div className="flex items-center gap-8 h-full px-5">
            <div className="flex flex-col items-start">
              <div className="panel-label mb-1">Funding Rate (8h)</div>
              <div
                className="data-value font-bold"
                style={{ fontSize: 24, color: fundingColor, lineHeight: 1, textShadow: `0 0 12px ${fundingColor}30` }}
              >
                {formatFunding(fundingRate)}
              </div>
              <div
                className="text-[9px] mt-1.5"
                style={{ color: COLORS.textSecondary, fontFamily: 'IBM Plex Sans, sans-serif' }}
              >
                {(fundingRate ?? 0) > 0
                  ? 'Longs paying shorts — market overbought'
                  : (fundingRate ?? 0) < 0
                  ? 'Shorts paying longs — market oversold'
                  : 'Neutral funding environment'}
              </div>
            </div>

            {/* Annualized */}
            <div
              className="flex flex-col pl-6"
              style={{ borderLeft: `1px solid ${COLORS.border}` }}
            >
              <div className="panel-label mb-1" style={{ fontSize: 8 }}>ANNUALIZED</div>
              <div
                className="data-value font-semibold"
                style={{ fontSize: 14, color: fundingColor }}
              >
                {fundingRate != null
                  ? `${((fundingRate * 3 * 365) * 100).toFixed(1)}%`
                  : '--'}
              </div>
            </div>
          </div>
        )}

        {/* ── OI ─────────────────────────────────── */}
        {activeTab === 'OI' && (
          <div className="flex items-center gap-8 h-full px-5">
            <div className="flex flex-col items-start">
              <div className="panel-label mb-1">Open Interest</div>
              <div
                className="data-value font-bold"
                style={{ fontSize: 24, color: COLORS.text, lineHeight: 1 }}
              >
                {formatCompact(openInterest)}
              </div>
              <div
                className="data-value text-[10px] mt-1"
                style={{ color: (oiDelta ?? 0) >= 0 ? COLORS.long : COLORS.short }}
              >
                {formatPct(oiDelta)} vs 24h ago
              </div>
            </div>

            <div
              className="flex flex-col pl-6"
              style={{ borderLeft: `1px solid ${COLORS.border}` }}
            >
              <div className="panel-label mb-1" style={{ fontSize: 8 }}>TREND</div>
              <div
                className="text-[11px] font-semibold"
                style={{
                  color: (oiDelta ?? 0) > 2 ? COLORS.long : (oiDelta ?? 0) < -2 ? COLORS.short : COLORS.textSecondary,
                  fontFamily: 'IBM Plex Sans, sans-serif',
                }}
              >
                {(oiDelta ?? 0) > 2 ? 'Rising — conviction' : (oiDelta ?? 0) < -2 ? 'Falling — unwinding' : 'Stable'}
              </div>
            </div>
          </div>
        )}

        {/* ── News ───────────────────────────────── */}
        {activeTab === 'News' && (
          <div className="h-full overflow-y-auto">
            {news && news.length > 0 ? (
              news.slice(0, 8).map((a, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 px-3 py-1.5 row-hover"
                  style={{ borderBottom: `1px solid ${COLORS.border}` }}
                >
                  <span
                    className="flex-shrink-0 text-[9px] font-semibold uppercase pt-px"
                    style={{
                      color: COLORS.accent,
                      fontFamily: 'IBM Plex Sans, sans-serif',
                      letterSpacing: '0.04em',
                      minWidth: 50,
                    }}
                  >
                    {a.source}
                  </span>
                  <span
                    className="text-[10px] leading-snug"
                    style={{ color: COLORS.textSecondary }}
                  >
                    {a.title}
                  </span>
                </div>
              ))
            ) : (
              <div className="flex items-center px-4 h-full text-[10px]" style={{ color: COLORS.textMuted }}>
                Loading news...
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
