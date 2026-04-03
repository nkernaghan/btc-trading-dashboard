'use client';

import { useDashboardStore } from '@/stores/dashboard';
import { VOTE_COLORS } from '@/lib/constants';
import { formatPrice } from '@/lib/format';

export default function SignalPanel() {
  const { signal, votes, warnings } = useDashboardStore();

  const directionColor =
    signal?.direction === 'LONG'
      ? 'text-[#00ff88]'
      : signal?.direction === 'SHORT'
      ? 'text-[#ff4444]'
      : 'text-[#888]';

  const scoreColor =
    signal?.direction === 'LONG'
      ? '#00ff88'
      : signal?.direction === 'SHORT'
      ? '#ff4444'
      : '#888';

  return (
    <div className="flex flex-col h-full overflow-y-auto bg-[#12122a] border-l border-[#2a2a4a] p-3">
      <h2 className="text-xs text-[#888] uppercase tracking-wider mb-3">Signal</h2>

      {/* Composite Score */}
      <div className="text-center mb-4">
        <div className="text-4xl font-bold" style={{ color: scoreColor }}>
          {signal ? (signal.composite_score ?? 0).toFixed(1) : '--'}
        </div>
        <div className={`text-lg font-bold ${directionColor}`}>
          {signal?.direction || 'WAIT'}
        </div>
        <div className="text-xs text-[#888] mt-1">
          {signal ? `${signal.confluence_count ?? signal.confluence ?? 0}/3 confluence` : '--'}
        </div>
        <div className="text-xs text-[#888]">
          Strength: {signal?.strength || '--'}
        </div>
      </div>

      {/* Trade Recommendation */}
      {signal && signal.direction !== 'WAIT' && (
        <div className="border border-[#2a2a4a] rounded p-2 mb-4 text-xs">
          <div className="text-[#888] uppercase tracking-wider mb-2">Trade Setup</div>
          <div className="grid grid-cols-2 gap-1">
            <span className="text-[#888]">Entry:</span>
            <span>{formatPrice(signal.entry_low ?? signal.entry ?? 0)}</span>
            <span className="text-[#888]">SL:</span>
            <span className="text-[#ff4444]">{formatPrice(signal.stop_loss)}</span>
            <span className="text-[#888]">TP1:</span>
            <span className="text-[#00ff88]">{formatPrice(signal.take_profit_1)}</span>
            <span className="text-[#888]">TP2:</span>
            <span className="text-[#00ff88]">{formatPrice(signal.take_profit_2)}</span>
            <span className="text-[#888]">Leverage:</span>
            <span>{signal.recommended_leverage ?? signal.leverage ?? 0}x</span>
            <span className="text-[#888]">Liq:</span>
            <span className="text-[#ff8800]">{formatPrice(signal.liquidation_price)}</span>
            <span className="text-[#888]">R:R:</span>
            <span className="text-[#4488ff]">{(signal.risk_reward_ratio ?? signal.risk_reward ?? 0).toFixed(2)}</span>
          </div>
        </div>
      )}

      {/* Indicator Votes */}
      <div className="mb-4">
        <div className="text-xs text-[#888] uppercase tracking-wider mb-2">Votes</div>
        <div className="space-y-1">
          {(votes.length > 0 ? votes : signal?.votes || []).map((v, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <span
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: VOTE_COLORS[v.vote] }}
              />
              <span className="text-[#888] truncate flex-1">{v.name}</span>
              <span style={{ color: VOTE_COLORS[v.vote] }}>{v.vote.replace('_', ' ')}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Warnings */}
      {warnings.length > 0 && (
        <div>
          <div className="text-xs text-[#ff8800] uppercase tracking-wider mb-2">Warnings</div>
          <div className="space-y-1">
            {warnings.map((w, i) => (
              <div key={i} className="text-xs text-[#ff8800] flex items-start gap-1">
                <span className="flex-shrink-0">!</span>
                <span>{w}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
