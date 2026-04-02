'use client';

import { useDashboardStore } from '@/stores/dashboard';
import { formatPrice, formatPct } from '@/lib/format';

export default function PositionTracker() {
  const { position } = useDashboardStore();

  if (!position) {
    return (
      <div className="p-3 border-t border-[#2a2a4a]">
        <div className="text-xs text-[#888] uppercase tracking-wider mb-1">Position</div>
        <div className="text-xs text-[#888]">No active position</div>
      </div>
    );
  }

  const pnlPct = position.pnl_pct ?? position.unrealized_pnl_pct ?? 0;
  const pnlUsd = position.pnl_usd ?? position.unrealized_pnl ?? 0;
  const fundingPaid = position.funding_paid ?? position.accumulated_funding ?? 0;
  const currentPrice = position.current_price ?? 0;
  const liqPrice = position.liquidation_price ?? 0;
  const distToLiq = position.distance_to_liq_pct ?? 0;
  const breakeven = position.breakeven ?? position.breakeven_price ?? 0;

  const pnlColor = pnlPct >= 0 ? 'text-[#00ff88]' : 'text-[#ff4444]';
  const dirColor = position.direction === 'LONG' ? 'text-[#00ff88]' : 'text-[#ff4444]';

  return (
    <div className="p-3 border-t border-[#2a2a4a]">
      <div className="text-xs text-[#888] uppercase tracking-wider mb-2">Position</div>

      <div className="flex items-center gap-2 mb-2">
        <span className={`text-sm font-bold ${dirColor}`}>{position.direction}</span>
        <span className="text-xs text-[#888]">{position.leverage}x</span>
      </div>

      <div className="grid grid-cols-2 gap-1 text-[10px]">
        <span className="text-[#888]">Entry:</span>
        <span>{formatPrice(position.entry_price)}</span>

        <span className="text-[#888]">Current:</span>
        <span>{formatPrice(currentPrice)}</span>

        <span className="text-[#888]">PnL:</span>
        <span className={pnlColor}>
          {formatPct(pnlPct)} (${pnlUsd.toFixed(2)})
        </span>

        <span className="text-[#888]">Liq Price:</span>
        <span className="text-[#ff8800]">{formatPrice(liqPrice)}</span>

        <span className="text-[#888]">Dist to Liq:</span>
        <span className="text-[#ff8800]">{formatPct(distToLiq)}</span>

        <span className="text-[#888]">Funding:</span>
        <span>${fundingPaid.toFixed(4)}</span>

        <span className="text-[#888]">Breakeven:</span>
        <span>{formatPrice(breakeven)}</span>
      </div>
    </div>
  );
}
