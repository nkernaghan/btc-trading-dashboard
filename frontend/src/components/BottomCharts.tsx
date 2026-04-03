'use client';

import { useState } from 'react';
import { useDashboardStore } from '@/stores/dashboard';
import { formatFunding, formatCompact, formatPct } from '@/lib/format';
import { COLORS } from '@/lib/constants';
import { calcVolumeProfile, calcLiquidationLevels } from '@/lib/indicators';

const TABS = ['Macro', 'Sentiment', 'Funding', 'OI', 'Vol Profile', 'Liq Levels', 'News'] as const;
type Tab = typeof TABS[number];

const MACRO_LABELS: Record<string, string> = {
  DXY:    'DXY',
  SPX:    'SPX',
  NQ:     'NQ',
  US10Y:  'US10Y',
  GOLD:   'Gold',
  BTC_DOM:'BTC.D',
};

function MacroCell({ label, price, changePct }: { label: string; price: number; changePct: number }) {
  const positive    = changePct >= 0;
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
      <div className="data-value text-[9px] font-medium" style={{ color: changeColor }}>
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
        style={{ color, fontFamily: 'Inter, sans-serif', letterSpacing: '0.05em' }}
      >
        {label}
      </div>
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

// ─── Volume Profile panel ──────────────────────────────────────────────────
function VolumeProfilePanel() {
  const { candles } = useDashboardStore();

  if (candles.length === 0) {
    return (
      <div className="flex items-center px-4 h-full text-[10px]" style={{ color: COLORS.textMuted }}>
        Loading candle data...
      </div>
    );
  }

  const buckets = calcVolumeProfile(candles, 20);
  const maxVol  = Math.max(...buckets.map((b) => b.volume));

  // Sort descending by price so the highest price is at the top
  const sorted = [...buckets].reverse();

  return (
    <div
      className="flex gap-3 h-full overflow-hidden px-3 py-2"
      style={{ alignItems: 'stretch' }}
    >
      {/* Bar chart */}
      <div className="flex flex-col justify-between flex-1 gap-px overflow-hidden" style={{ minWidth: 0 }}>
        {sorted.map((bucket, i) => {
          const barPct = maxVol > 0 ? (bucket.volume / maxVol) * 100 : 0;
          return (
            <div
              key={i}
              className="flex items-center gap-1.5 flex-1"
              style={{ minHeight: 0 }}
            >
              {/* Price label */}
              <div
                className="flex-shrink-0 text-right"
                style={{
                  width:      62,
                  fontSize:   8,
                  fontFamily: 'Inter, sans-serif',
                  color:      bucket.isPoc ? COLORS.btc : COLORS.textSecondary,
                  fontWeight: bucket.isPoc ? 700 : 400,
                  lineHeight: 1,
                }}
              >
                {bucket.priceMid.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>

              {/* Bar */}
              <div
                className="flex-1 rounded-sm overflow-hidden"
                style={{ height: '70%', background: COLORS.borderSubtle, minWidth: 0 }}
              >
                <div
                  className="h-full rounded-sm transition-all duration-300"
                  style={{
                    width:      `${barPct}%`,
                    background: bucket.isPoc
                      ? COLORS.btc
                      : `rgba(41, 98, 255, 0.35)`,
                  }}
                />
              </div>

              {/* POC label */}
              {bucket.isPoc && (
                <div
                  className="flex-shrink-0"
                  style={{
                    fontSize:    8,
                    fontFamily:  'Inter, sans-serif',
                    color:       COLORS.btc,
                    fontWeight:  700,
                    letterSpacing: '0.04em',
                  }}
                >
                  POC
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div
        className="flex flex-col justify-center gap-1.5 flex-shrink-0"
        style={{ borderLeft: `1px solid ${COLORS.border}`, paddingLeft: 10 }}
      >
        <div className="panel-label" style={{ fontSize: 8 }}>VOLUME PROFILE</div>
        <div
          className="text-[9px]"
          style={{ color: COLORS.textSecondary, fontFamily: 'Inter, sans-serif', maxWidth: 80 }}
        >
          {candles.length} candles
        </div>
        <div className="flex items-center gap-1 mt-1">
          <div
            className="rounded-sm"
            style={{ width: 8, height: 8, background: COLORS.btc }}
          />
          <div className="text-[8px]" style={{ color: COLORS.textMuted, fontFamily: 'Inter, sans-serif' }}>
            POC
          </div>
        </div>
        <div className="flex items-center gap-1">
          <div
            className="rounded-sm"
            style={{ width: 8, height: 8, background: 'rgba(41, 98, 255, 0.35)' }}
          />
          <div className="text-[8px]" style={{ color: COLORS.textMuted, fontFamily: 'Inter, sans-serif' }}>
            Volume
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Liquidation Levels panel ──────────────────────────────────────────────
function LiquidationLevelsPanel() {
  const { price } = useDashboardStore();

  if (!price || price === 0) {
    return (
      <div className="flex items-center px-4 h-full text-[10px]" style={{ color: COLORS.textMuted }}>
        Waiting for price data...
      </div>
    );
  }

  const levels = calcLiquidationLevels(price, [5, 10, 20, 25, 30, 40]);
  const maxDistPct = Math.max(...levels.map((l) => l.shortDistancePct));

  return (
    <div className="flex h-full overflow-hidden px-3 py-2 gap-4">
      {/* Long liquidations */}
      <div className="flex flex-col flex-1 gap-1 overflow-hidden" style={{ minWidth: 0 }}>
        <div
          className="flex-shrink-0 mb-1"
          style={{ fontSize: 8, fontFamily: 'Inter, sans-serif', color: COLORS.long, fontWeight: 700, letterSpacing: '0.05em' }}
        >
          LONG LIQUIDATIONS
        </div>
        {levels.map((lv) => {
          const barPct = maxDistPct > 0 ? (lv.longDistancePct / maxDistPct) * 100 : 0;
          return (
            <div key={`long-${lv.leverage}`} className="flex items-center gap-1.5 flex-1" style={{ minHeight: 0 }}>
              <div
                className="flex-shrink-0 text-right font-semibold"
                style={{ width: 22, fontSize: 9, fontFamily: 'Inter, sans-serif', color: COLORS.textSecondary }}
              >
                {lv.leverage}x
              </div>
              <div
                className="flex-1 rounded-sm overflow-hidden"
                style={{ height: '60%', background: COLORS.borderSubtle, minWidth: 0 }}
              >
                <div
                  className="h-full rounded-sm"
                  style={{
                    width:      `${barPct}%`,
                    background: 'rgba(38, 166, 154, 0.45)',
                  }}
                />
              </div>
              <div
                className="flex-shrink-0 text-right"
                style={{ width: 52, fontSize: 8, fontFamily: 'Inter, sans-serif', color: COLORS.long }}
              >
                ${lv.longLiq.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div
                className="flex-shrink-0"
                style={{ width: 34, fontSize: 8, fontFamily: 'Inter, sans-serif', color: COLORS.textMuted }}
              >
                -{lv.longDistancePct.toFixed(1)}%
              </div>
            </div>
          );
        })}
      </div>

      {/* Divider + current price */}
      <div
        className="flex flex-col items-center justify-center flex-shrink-0 px-3"
        style={{ borderLeft: `1px solid ${COLORS.border}`, borderRight: `1px solid ${COLORS.border}` }}
      >
        <div className="panel-label mb-1" style={{ fontSize: 8 }}>PRICE</div>
        <div
          className="data-value font-bold"
          style={{ fontSize: 13, color: COLORS.text, lineHeight: 1 }}
        >
          ${price.toLocaleString(undefined, { maximumFractionDigits: 0 })}
        </div>
      </div>

      {/* Short liquidations */}
      <div className="flex flex-col flex-1 gap-1 overflow-hidden" style={{ minWidth: 0 }}>
        <div
          className="flex-shrink-0 mb-1"
          style={{ fontSize: 8, fontFamily: 'Inter, sans-serif', color: COLORS.short, fontWeight: 700, letterSpacing: '0.05em' }}
        >
          SHORT LIQUIDATIONS
        </div>
        {levels.map((lv) => {
          const barPct = maxDistPct > 0 ? (lv.shortDistancePct / maxDistPct) * 100 : 0;
          return (
            <div key={`short-${lv.leverage}`} className="flex items-center gap-1.5 flex-1" style={{ minHeight: 0 }}>
              <div
                className="flex-shrink-0 text-right font-semibold"
                style={{ width: 22, fontSize: 9, fontFamily: 'Inter, sans-serif', color: COLORS.textSecondary }}
              >
                {lv.leverage}x
              </div>
              <div
                className="flex-1 rounded-sm overflow-hidden"
                style={{ height: '60%', background: COLORS.borderSubtle, minWidth: 0 }}
              >
                <div
                  className="h-full rounded-sm"
                  style={{
                    width:      `${barPct}%`,
                    background: 'rgba(239, 83, 80, 0.45)',
                  }}
                />
              </div>
              <div
                className="flex-shrink-0 text-right"
                style={{ width: 52, fontSize: 8, fontFamily: 'Inter, sans-serif', color: COLORS.short }}
              >
                ${lv.shortLiq.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div
                className="flex-shrink-0"
                style={{ width: 34, fontSize: 8, fontFamily: 'Inter, sans-serif', color: COLORS.textMuted }}
              >
                +{lv.shortDistancePct.toFixed(1)}%
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────
export default function BottomCharts() {
  const [activeTab, setActiveTab] = useState<Tab>('Macro');
  const { fundingRate, openInterest, oiDelta, indicators } = useDashboardStore();

  const macro      = (indicators as any)?.macro_data as Record<string, { price: number; change_pct: number }> | undefined;
  const fearGreed  = (indicators as any)?.sentiment_fear_greed as { value: number; classification: string } | undefined;
  const dominance  = (indicators as any)?.sentiment_btc_dominance as { btc_dominance: number } | undefined;
  const news       = (indicators as any)?.news_articles as { title: string; source: string; url?: string }[] | undefined;

  const fundingColor =
    Math.abs(fundingRate ?? 0) > 0.001
      ? COLORS.warn
      : (fundingRate ?? 0) >= 0
      ? COLORS.long
      : COLORS.short;

  return (
    <div className="flex flex-col h-full" style={{ background: COLORS.panel }}>
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
                color:       active ? COLORS.accent : COLORS.textMuted,
                background:  active ? 'rgba(74,124,204,0.06)' : 'transparent',
                fontFamily:  'Inter, sans-serif',
                letterSpacing: '0.04em',
                borderRight: `1px solid ${COLORS.border}`,
                whiteSpace:  'nowrap',
              }}
            >
              {tab}
              {active && (
                <div
                  style={{
                    position:   'absolute',
                    bottom:     0,
                    left:       0,
                    right:      0,
                    height:     1,
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
                style={{ color: COLORS.textSecondary, fontFamily: 'Inter, sans-serif' }}
              >
                {(fundingRate ?? 0) > 0
                  ? 'Longs paying shorts — market overbought'
                  : (fundingRate ?? 0) < 0
                  ? 'Shorts paying longs — market oversold'
                  : 'Neutral funding environment'}
              </div>
            </div>
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
                  fontFamily: 'Inter, sans-serif',
                }}
              >
                {(oiDelta ?? 0) > 2 ? 'Rising — conviction' : (oiDelta ?? 0) < -2 ? 'Falling — unwinding' : 'Stable'}
              </div>
            </div>
          </div>
        )}

        {/* ── Volume Profile ──────────────────────── */}
        {activeTab === 'Vol Profile' && <VolumeProfilePanel />}

        {/* ── Liquidation Levels ──────────────────── */}
        {activeTab === 'Liq Levels' && <LiquidationLevelsPanel />}

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
                      color:          COLORS.accent,
                      fontFamily:     'Inter, sans-serif',
                      letterSpacing:  '0.04em',
                      minWidth:       50,
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
