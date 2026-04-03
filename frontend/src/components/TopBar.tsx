'use client';

import { useDashboardStore } from '@/stores/dashboard';
import { formatPrice, formatPct, formatFunding } from '@/lib/format';
import { TIMEFRAMES, COLORS } from '@/lib/constants';

export default function TopBar() {
  const { price, price24hChange, high24h, low24h, fundingRate, openInterest, oiDelta, timeframe, setTimeframe } =
    useDashboardStore();

  return (
    <div className="flex items-center h-10 px-4 border-b" style={{ background: COLORS.panel, borderColor: COLORS.border }}>
      <div className="flex items-center gap-3 mr-6">
        <span className="text-[11px] font-semibold tracking-wide" style={{ color: COLORS.btc }}>BTC-PERP</span>
        <span className="text-[15px] font-semibold" style={{ color: COLORS.text, fontVariantNumeric: 'tabular-nums' }}>
          {formatPrice(price)}
        </span>
        <span className="text-[11px]" style={{ color: (price24hChange ?? 0) >= 0 ? COLORS.long : COLORS.short, fontVariantNumeric: 'tabular-nums' }}>
          {formatPct(price24hChange)}
        </span>
      </div>

      <div className="flex items-center gap-3 mr-6 text-[10px]" style={{ color: COLORS.textSecondary }}>
        <span>H <span style={{ color: COLORS.text }}>{formatPrice(high24h)}</span></span>
        <span>L <span style={{ color: COLORS.text }}>{formatPrice(low24h)}</span></span>
      </div>

      <div className="flex items-center gap-0.5 mr-auto">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf}
            onClick={() => setTimeframe(tf)}
            className="px-2 py-0.5 text-[10px] font-medium rounded-sm transition-colors"
            style={{
              background: timeframe === tf ? COLORS.surface : 'transparent',
              color: timeframe === tf ? COLORS.text : COLORS.textMuted,
              border: timeframe === tf ? `1px solid ${COLORS.border}` : '1px solid transparent',
            }}
          >
            {tf}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-5 text-[10px]" style={{ color: COLORS.textSecondary }}>
        <span>Funding <span style={{ color: (fundingRate ?? 0) > 0.0005 ? COLORS.warn : COLORS.text }}>{formatFunding(fundingRate)}</span></span>
        <span>OI <span style={{ color: COLORS.text }}>{openInterest > 0 ? `$${(openInterest / 1e9).toFixed(1)}B` : '--'}</span></span>
      </div>
    </div>
  );
}
