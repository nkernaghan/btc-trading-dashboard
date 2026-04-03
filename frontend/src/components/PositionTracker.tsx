'use client';

import { useDashboardStore } from '@/stores/dashboard';
import { formatPrice, formatPct } from '@/lib/format';
import { COLORS } from '@/lib/constants';

export default function PositionTracker() {
  const { position } = useDashboardStore();

  if (!position) {
    return (
      <div
        className="flex items-center justify-between px-3 py-2.5"
        style={{ background: COLORS.panel }}
      >
        <span className="panel-label">Position</span>
        <span className="text-[10px]" style={{ color: COLORS.textMuted }}>No active position</span>
      </div>
    );
  }

  const pnlPct = position.pnl_pct ?? position.unrealized_pnl_pct ?? 0;
  const pnlUsd = position.pnl_usd ?? position.unrealized_pnl ?? 0;
  const liqPrice = position.liquidation_price ?? 0;
  const distToLiq = position.distance_to_liq_pct ?? 0;
  const fundingPaid = position.funding_paid ?? position.accumulated_funding ?? 0;
  const breakeven = position.breakeven ?? position.breakeven_price ?? 0;
  const currentPrice = position.current_price ?? 0;

  const pnlColor = pnlPct >= 0 ? COLORS.long : COLORS.short;
  const dirColor = position.direction === 'LONG' ? COLORS.long : COLORS.short;
  const liqDangerColor = distToLiq < 3 ? COLORS.short : distToLiq < 8 ? COLORS.warn : COLORS.textSecondary;
  const pnlPositive = pnlPct >= 0;

  return (
    <div style={{ background: COLORS.panel }}>
      {/* Header row */}
      <div
        className="flex items-center justify-between px-3 py-2"
        style={{ borderBottom: `1px solid ${COLORS.border}` }}
      >
        <span className="panel-label">Position</span>
        <div className="flex items-center gap-2">
          <span
            className="text-[10px] font-semibold px-1.5 py-0.5 rounded-sm"
            style={{
              color: dirColor,
              background: `${dirColor}15`,
              fontFamily: 'Inter, sans-serif',
              letterSpacing: '0.06em',
            }}
          >
            {position.direction}
          </span>
          <span className="text-[10px]" style={{ color: COLORS.textSecondary }}>
            {position.leverage}x
          </span>
        </div>
      </div>

      {/* Grid of metrics */}
      <div
        className="grid px-3 py-2 gap-x-4 gap-y-1.5"
        style={{ gridTemplateColumns: '1fr 1fr' }}
      >
        {/* Entry */}
        <div className="flex flex-col">
          <span className="data-label text-[9px] mb-0.5">Entry</span>
          <span className="data-value text-[11px] font-medium" style={{ color: COLORS.text }}>
            {formatPrice(position.entry_price)}
          </span>
        </div>

        {/* Current */}
        <div className="flex flex-col">
          <span className="data-label text-[9px] mb-0.5">Current</span>
          <span className="data-value text-[11px] font-medium" style={{ color: COLORS.text }}>
            {formatPrice(currentPrice)}
          </span>
        </div>

        {/* PnL */}
        <div
          className="col-span-2 flex items-center justify-between py-1 px-2 rounded-sm"
          style={{ background: pnlPositive ? 'rgba(45,159,111,0.07)' : 'rgba(199,75,75,0.07)' }}
        >
          <span className="data-label text-[9px]">Unrealized PnL</span>
          <div className="flex items-center gap-1.5">
            <span className="data-value text-[11px] font-semibold" style={{ color: pnlColor }}>
              {pnlPositive ? '+' : ''}${pnlUsd.toFixed(2)}
            </span>
            <span className="data-value text-[10px]" style={{ color: pnlColor }}>
              ({formatPct(pnlPct)})
            </span>
          </div>
        </div>

        {/* Liq */}
        <div className="flex flex-col">
          <span className="data-label text-[9px] mb-0.5">Liq. Price</span>
          <span className="data-value text-[11px] font-medium" style={{ color: COLORS.warn }}>
            {formatPrice(liqPrice)}
          </span>
        </div>

        {/* Dist to Liq */}
        <div className="flex flex-col">
          <span className="data-label text-[9px] mb-0.5">Dist. to Liq</span>
          <span className="data-value text-[11px] font-medium" style={{ color: liqDangerColor }}>
            {formatPct(distToLiq)}
          </span>
        </div>

        {/* Breakeven */}
        <div className="flex flex-col">
          <span className="data-label text-[9px] mb-0.5">Breakeven</span>
          <span className="data-value text-[11px]" style={{ color: COLORS.textSecondary }}>
            {formatPrice(breakeven)}
          </span>
        </div>

        {/* Funding */}
        <div className="flex flex-col">
          <span className="data-label text-[9px] mb-0.5">Funding Paid</span>
          <span
            className="data-value text-[11px]"
            style={{ color: fundingPaid < 0 ? COLORS.short : COLORS.textSecondary }}
          >
            ${fundingPaid.toFixed(4)}
          </span>
        </div>
      </div>
    </div>
  );
}
