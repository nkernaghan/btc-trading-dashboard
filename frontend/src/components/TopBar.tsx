'use client';

import { useDashboardStore } from '@/stores/dashboard';
import { formatPrice, formatPct, formatFunding, getSession } from '@/lib/format';
import { TIMEFRAMES, COLORS } from '@/lib/constants';

const SESSION_LABELS: Record<string, { label: string; color: string }> = {
  ASIA: { label: 'ASIA', color: '#c49a3c' },
  LONDON: { label: 'LDN', color: '#4a7ccc' },
  NEW_YORK: { label: 'NYC', color: '#2d9f6f' },
  OVERLAP: { label: 'OVL', color: '#c49a3c' },
};

export default function TopBar() {
  const { price, price24hChange, high24h, low24h, fundingRate, openInterest, oiDelta, timeframe, setTimeframe } =
    useDashboardStore();

  const changePositive = (price24hChange ?? 0) >= 0;
  const changeColor = changePositive ? COLORS.long : COLORS.short;
  const fundingHigh = Math.abs(fundingRate ?? 0) > 0.0005;
  const session = getSession();
  const sessionInfo = SESSION_LABELS[session] ?? { label: session, color: COLORS.textSecondary };

  return (
    <div
      className="flex items-center h-10 px-4 flex-shrink-0"
      style={{
        background: COLORS.panel,
        borderBottom: `1px solid ${COLORS.border}`,
        minWidth: 0,
      }}
    >
      {/* Instrument + Price */}
      <div className="flex items-center gap-0 mr-5 flex-shrink-0">
        <div className="flex items-center gap-3">
          {/* BTC label */}
          <div className="flex items-center gap-1.5">
            <div
              className="w-1.5 h-1.5 rounded-full flex-shrink-0"
              style={{ background: COLORS.btc }}
            />
            <span
              className="text-[10px] font-semibold tracking-widest uppercase"
              style={{ color: COLORS.btc, fontFamily: 'IBM Plex Sans, sans-serif' }}
            >
              BTC-PERP
            </span>
          </div>

          {/* Vertical rule */}
          <div className="panel-divider-v h-5" />

          {/* Price */}
          <span
            className="text-[16px] font-semibold data-value"
            style={{ color: COLORS.text, letterSpacing: '-0.01em' }}
          >
            {formatPrice(price)}
          </span>

          {/* 24h change badge */}
          <span
            className="text-[11px] font-medium data-value px-1.5 py-0.5 rounded-sm"
            style={{
              color: changeColor,
              background: changePositive ? 'rgba(45,159,111,0.1)' : 'rgba(199,75,75,0.1)',
            }}
          >
            {changePositive ? '+' : ''}{formatPct(price24hChange)}
          </span>
        </div>
      </div>

      {/* H/L */}
      <div
        className="flex items-center gap-4 mr-5 text-[10px] flex-shrink-0"
        style={{ color: COLORS.textSecondary }}
      >
        <span>
          <span className="panel-label mr-1" style={{ fontSize: 9 }}>H</span>
          <span className="data-value" style={{ color: COLORS.text }}>{formatPrice(high24h)}</span>
        </span>
        <span>
          <span className="panel-label mr-1" style={{ fontSize: 9 }}>L</span>
          <span className="data-value" style={{ color: COLORS.text }}>{formatPrice(low24h)}</span>
        </span>
      </div>

      <div className="panel-divider-v h-5 mr-5 flex-shrink-0" />

      {/* Timeframe Buttons */}
      <div className="flex items-center gap-px mr-auto">
        {TIMEFRAMES.map((tf) => {
          const active = timeframe === tf;
          return (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className="px-2.5 py-1 text-[10px] font-medium rounded-sm transition-all duration-100"
              style={{
                background: active ? 'rgba(74,124,204,0.15)' : 'transparent',
                color: active ? COLORS.accent : COLORS.textMuted,
                border: active ? `1px solid rgba(74,124,204,0.3)` : '1px solid transparent',
                fontFamily: 'IBM Plex Sans, sans-serif',
                letterSpacing: '0.05em',
              }}
            >
              {tf}
            </button>
          );
        })}
      </div>

      {/* Right metrics */}
      <div className="flex items-center gap-0 text-[10px] flex-shrink-0">
        {/* Funding */}
        <div
          className="flex items-center gap-1.5 px-3"
          style={{ borderLeft: `1px solid ${COLORS.border}` }}
        >
          <span className="panel-label">FUND</span>
          <span
            className="data-value font-medium"
            style={{
              color: fundingHigh ? COLORS.warn : (fundingRate ?? 0) >= 0 ? COLORS.long : COLORS.short,
            }}
          >
            {formatFunding(fundingRate)}
          </span>
        </div>

        {/* OI */}
        <div
          className="flex items-center gap-1.5 px-3"
          style={{ borderLeft: `1px solid ${COLORS.border}` }}
        >
          <span className="panel-label">OI</span>
          <span className="data-value font-medium" style={{ color: COLORS.text }}>
            {openInterest > 0 ? `$${(openInterest / 1e9).toFixed(2)}B` : '--'}
          </span>
          {(oiDelta ?? 0) !== 0 && (
            <span
              className="data-value text-[9px]"
              style={{ color: (oiDelta ?? 0) >= 0 ? COLORS.long : COLORS.short }}
            >
              {(oiDelta ?? 0) >= 0 ? '+' : ''}{formatPct(oiDelta)}
            </span>
          )}
        </div>

        {/* Session */}
        <div
          className="flex items-center gap-1.5 px-3"
          style={{ borderLeft: `1px solid ${COLORS.border}` }}
        >
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: sessionInfo.color, boxShadow: `0 0 4px ${sessionInfo.color}` }}
          />
          <span
            className="panel-label"
            style={{ color: sessionInfo.color }}
          >
            {sessionInfo.label}
          </span>
        </div>
      </div>
    </div>
  );
}
