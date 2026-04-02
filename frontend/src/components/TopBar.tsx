'use client';

import { useDashboardStore } from '@/stores/dashboard';
import { TIMEFRAMES } from '@/lib/constants';
import { formatPrice, formatPct, formatCompact, formatFunding, getSession, getSessionEmoji } from '@/lib/format';
import { Timeframe } from '@/lib/types';

export default function TopBar() {
  const {
    price, price24hChange, high24h, low24h,
    fundingRate, openInterest, oiDelta,
    timeframe, setTimeframe,
  } = useDashboardStore();

  const session = getSession();
  const changeColor = price24hChange >= 0 ? 'text-[#00ff88]' : 'text-[#ff4444]';

  return (
    <div className="flex items-center justify-between px-4 py-2 border-b border-[#2a2a4a] bg-[#12122a]">
      {/* Left: Price info */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <span className="text-[#f7931a] font-bold text-lg">BTC/USDT</span>
          <span className="text-xl font-bold">{formatPrice(price)}</span>
          <span className={`text-sm ${changeColor}`}>{formatPct(price24hChange)}</span>
        </div>
        <div className="flex items-center gap-4 text-xs text-[#888]">
          <span>H: <span className="text-[#e0e0e0]">{formatPrice(high24h)}</span></span>
          <span>L: <span className="text-[#e0e0e0]">{formatPrice(low24h)}</span></span>
        </div>
      </div>

      {/* Center: Timeframes */}
      <div className="flex items-center gap-1">
        {TIMEFRAMES.map((tf: Timeframe) => (
          <button
            key={tf}
            onClick={() => setTimeframe(tf)}
            className={`px-3 py-1 text-xs rounded transition-colors ${
              timeframe === tf
                ? 'bg-[#4488ff] text-white'
                : 'text-[#888] hover:text-[#e0e0e0] hover:bg-[#1a1a2e]'
            }`}
          >
            {tf}
          </button>
        ))}
      </div>

      {/* Right: Session, funding, OI */}
      <div className="flex items-center gap-6 text-xs">
        <div className="flex items-center gap-1">
          <span>{getSessionEmoji(session)}</span>
          <span className="text-[#888]">{session}</span>
        </div>
        <div>
          <span className="text-[#888]">Funding: </span>
          <span className={fundingRate >= 0 ? 'text-[#00ff88]' : 'text-[#ff4444]'}>
            {formatFunding(fundingRate)}
          </span>
        </div>
        <div>
          <span className="text-[#888]">OI: </span>
          <span className="text-[#e0e0e0]">{formatCompact(openInterest)}</span>
          <span className={`ml-1 ${oiDelta >= 0 ? 'text-[#00ff88]' : 'text-[#ff4444]'}`}>
            {formatPct(oiDelta)}
          </span>
        </div>
      </div>
    </div>
  );
}
