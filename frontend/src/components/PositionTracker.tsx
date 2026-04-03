'use client';

import { useDashboardStore } from '@/stores/dashboard';
import { formatPrice, formatPct } from '@/lib/format';
import { COLORS } from '@/lib/constants';

export default function PositionTracker() {
  const { position } = useDashboardStore();

  if (!position) {
    return (
      <div className="p-3" style={{ borderTop: `1px solid ${COLORS.border}` }}>
        <div className="text-[10px] font-medium tracking-widest uppercase mb-1" style={{ color: COLORS.textMuted, fontFamily: 'IBM Plex Sans, sans-serif' }}>
          Position
        </div>
        <div className="text-[10px]" style={{ color: COLORS.textMuted }}>No active position</div>
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

  return (
    <div className="p-3" style={{ borderTop: `1px solid ${COLORS.border}` }}>
      <div className="text-[10px] font-medium tracking-widest uppercase mb-2" style={{ color: COLORS.textMuted, fontFamily: 'IBM Plex Sans, sans-serif' }}>
        Position
      </div>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[11px] font-semibold" style={{ color: dirColor }}>{position.direction}</span>
        <span className="text-[10px]" style={{ color: COLORS.textSecondary }}>{position.leverage}x</span>
      </div>
      <div className="space-y-0.5 text-[10px]" style={{ fontVariantNumeric: 'tabular-nums' }}>
        {[
          ['Entry', formatPrice(position.entry_price), COLORS.text],
          ['Current', formatPrice(currentPrice), COLORS.text],
          ['PnL', `${formatPct(pnlPct)} ($${pnlUsd.toFixed(2)})`, pnlColor],
          ['Liq', formatPrice(liqPrice), COLORS.warn],
          ['Dist', formatPct(distToLiq), distToLiq < 3 ? COLORS.short : COLORS.textSecondary],
          ['Funding', `$${fundingPaid.toFixed(4)}`, COLORS.textSecondary],
          ['BE', formatPrice(breakeven), COLORS.textSecondary],
        ].map(([label, value, color]) => (
          <div key={label as string} className="flex justify-between">
            <span style={{ color: COLORS.textSecondary }}>{label}</span>
            <span style={{ color: color as string }}>{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
