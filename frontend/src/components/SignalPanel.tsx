'use client';

import { useDashboardStore } from '@/stores/dashboard';
import { VOTE_COLORS, COLORS } from '@/lib/constants';
import { formatPrice } from '@/lib/format';

export default function SignalPanel() {
  const { signal, votes, warnings } = useDashboardStore();

  const direction = signal?.direction ?? 'WAIT';
  const score = signal?.composite_score ?? 0;
  const dirColor = direction === 'LONG' ? COLORS.long : direction === 'SHORT' ? COLORS.short : COLORS.neutral;
  const dirBg = direction === 'LONG' ? 'rgba(45,159,111,0.06)' : direction === 'SHORT' ? 'rgba(199,75,75,0.06)' : 'transparent';

  return (
    <div className="flex flex-col h-full overflow-y-auto p-3" style={{ background: COLORS.panel, borderLeft: `1px solid ${COLORS.border}` }}>
      <div className="text-[10px] font-medium tracking-widest uppercase mb-3" style={{ color: COLORS.textMuted, fontFamily: 'IBM Plex Sans, sans-serif' }}>
        Signal
      </div>

      {/* Score */}
      <div className="text-center mb-4 py-3 rounded" style={{ background: dirBg }}>
        <div className="text-[28px] font-semibold" style={{ color: dirColor, fontVariantNumeric: 'tabular-nums' }}>
          {score > 0 ? score.toFixed(1) : '--'}
        </div>
        <div className="text-[13px] font-semibold tracking-wider" style={{ color: dirColor }}>
          {direction}
        </div>
        <div className="text-[10px] mt-1" style={{ color: COLORS.textMuted }}>
          {signal ? `${signal.confluence_count ?? 0}/3 confluence` : '--'}
          {signal?.strength ? ` \u00B7 ${signal.strength}` : ''}
        </div>
      </div>

      {/* Trade Setup */}
      {signal && direction !== 'WAIT' && (
        <div className="mb-4 py-2 px-2 rounded" style={{ border: `1px solid ${COLORS.border}`, background: COLORS.surface }}>
          <div className="text-[10px] font-medium tracking-widest uppercase mb-2" style={{ color: COLORS.textMuted, fontFamily: 'IBM Plex Sans, sans-serif' }}>
            Setup
          </div>
          <div className="space-y-1 text-[11px]" style={{ fontVariantNumeric: 'tabular-nums' }}>
            {[
              ['Entry', formatPrice(signal.entry_low ?? 0), COLORS.text],
              ['Stop', formatPrice(signal.stop_loss ?? 0), COLORS.short],
              ['TP1', formatPrice(signal.take_profit_1 ?? 0), COLORS.long],
              ['TP2', formatPrice(signal.take_profit_2 ?? 0), COLORS.long],
              ['Leverage', `${signal.recommended_leverage ?? 0}x`, COLORS.text],
              ['Liq', formatPrice(signal.liquidation_price ?? 0), COLORS.warn],
              ['R:R', `${(signal.risk_reward_ratio ?? 0).toFixed(2)}`, COLORS.accent],
            ].map(([label, value, color]) => (
              <div key={label as string} className="flex justify-between">
                <span style={{ color: COLORS.textSecondary }}>{label}</span>
                <span style={{ color: color as string }}>{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Votes */}
      <div className="mb-4">
        <div className="text-[10px] font-medium tracking-widest uppercase mb-2" style={{ color: COLORS.textMuted, fontFamily: 'IBM Plex Sans, sans-serif' }}>
          Votes
        </div>
        <div className="space-y-0.5">
          {(votes.length > 0 ? votes : signal?.votes ?? []).map((v, i) => (
            <div key={i} className="flex items-center justify-between text-[10px] py-0.5">
              <span style={{ color: COLORS.textSecondary }}>{v.name}</span>
              <span className="font-medium" style={{ color: VOTE_COLORS[v.vote] ?? COLORS.neutral }}>{v.vote}</span>
            </div>
          ))}
          {votes.length === 0 && !signal?.votes?.length && (
            <div className="text-[10px]" style={{ color: COLORS.textMuted }}>Awaiting data...</div>
          )}
        </div>
      </div>

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="mt-auto pt-2" style={{ borderTop: `1px solid ${COLORS.border}` }}>
          {warnings.map((w, i) => (
            <div key={i} className="text-[10px] py-0.5" style={{ color: COLORS.warn }}>{w}</div>
          ))}
        </div>
      )}
    </div>
  );
}
