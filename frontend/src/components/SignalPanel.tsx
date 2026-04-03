'use client';

import { useDashboardStore } from '@/stores/dashboard';
import { VOTE_COLORS, COLORS } from '@/lib/constants';
import { formatPrice } from '@/lib/format';
import type { IndicatorVote } from '@/lib/types';

function VoteDot({ vote }: { vote: string }) {
  const color = VOTE_COLORS[vote] ?? COLORS.neutral;
  return (
    <div
      style={{
        width: 5,
        height: 5,
        borderRadius: '50%',
        background: color,
        flexShrink: 0,
        boxShadow: vote !== 'NEUTRAL' ? `0 0 4px ${color}80` : undefined,
      }}
    />
  );
}

function ConfluenceDots({ count, total = 3 }: { count: number; total?: number }) {
  return (
    <div className="flex items-center gap-1">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          style={{
            width: 5,
            height: 5,
            borderRadius: '50%',
            background: i < count ? COLORS.accent : COLORS.border,
            boxShadow: i < count ? `0 0 4px ${COLORS.accent}60` : undefined,
          }}
        />
      ))}
    </div>
  );
}

function SetupRow({
  label,
  value,
  color,
  highlight,
}: {
  label: string;
  value: string;
  color: string;
  highlight?: boolean;
}) {
  return (
    <div
      className="flex items-center justify-between px-2 py-1 row-hover"
      style={{
        background: highlight ? `${color}08` : undefined,
        borderBottom: `1px solid ${COLORS.border}`,
      }}
    >
      <span className="data-label text-[10px]">{label}</span>
      <span className="data-value text-[11px] font-medium" style={{ color }}>
        {value}
      </span>
    </div>
  );
}

export default function SignalPanel() {
  const { signal, votes, warnings } = useDashboardStore();

  const direction = signal?.direction ?? 'WAIT';
  const score = signal?.composite_score ?? 0;
  const strength = signal?.strength ?? 'NONE';
  const confluence = signal?.confluence_count ?? 0;

  const dirColor =
    direction === 'LONG' ? COLORS.long : direction === 'SHORT' ? COLORS.short : COLORS.neutral;

  const dirBg =
    direction === 'LONG'
      ? 'rgba(45,159,111,0.06)'
      : direction === 'SHORT'
      ? 'rgba(199,75,75,0.06)'
      : 'rgba(75,80,96,0.04)';

  const glowClass =
    direction === 'LONG'
      ? 'score-glow-long'
      : direction === 'SHORT'
      ? 'score-glow-short'
      : '';

  const displayVotes: IndicatorVote[] =
    votes.length > 0 ? votes : (signal?.votes ?? []);

  const bullVotes = displayVotes.filter((v) => v.vote === 'BULL').length;
  const bearVotes = displayVotes.filter((v) => v.vote === 'BEAR').length;

  return (
    <div
      className="flex flex-col h-full overflow-hidden"
      style={{ background: COLORS.panel }}
    >
      {/* Panel header */}
      <div
        className="flex items-center justify-between px-3 py-2 flex-shrink-0"
        style={{ borderBottom: `1px solid ${COLORS.border}` }}
      >
        <span className="panel-label">Signal</span>
        <div className="flex items-center gap-1.5 text-[9px]" style={{ color: COLORS.textMuted }}>
          <span style={{ color: COLORS.long }}>{bullVotes}↑</span>
          <span style={{ color: COLORS.short }}>{bearVotes}↓</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Score Block */}
        <div
          className={`flex flex-col items-center justify-center py-5 ${glowClass}`}
          style={{ background: dirBg, borderBottom: `1px solid ${COLORS.border}` }}
        >
          {/* Direction label */}
          <div
            className="text-[9px] font-semibold tracking-widest uppercase mb-2 px-2 py-0.5 rounded-sm"
            style={{
              color: dirColor,
              background: `${dirColor}15`,
              fontFamily: 'IBM Plex Sans, sans-serif',
              letterSpacing: '0.15em',
            }}
          >
            {direction}
          </div>

          {/* Composite score */}
          <div
            className="data-value font-semibold"
            style={{
              fontSize: 38,
              lineHeight: 1,
              color: dirColor,
              letterSpacing: '-0.02em',
              textShadow: direction !== 'WAIT' ? `0 0 20px ${dirColor}40` : undefined,
            }}
          >
            {score > 0 ? score.toFixed(1) : '--'}
          </div>

          {/* Strength + Confluence */}
          <div className="flex items-center gap-3 mt-3">
            {strength !== 'NONE' && (
              <span
                className="text-[9px] font-semibold uppercase px-1.5 py-0.5 rounded-sm"
                style={{
                  color: strength === 'STRONG' ? dirColor : COLORS.textMuted,
                  background: strength === 'STRONG' ? `${dirColor}15` : COLORS.surface,
                  fontFamily: 'IBM Plex Sans, sans-serif',
                  letterSpacing: '0.08em',
                }}
              >
                {strength}
              </span>
            )}
            <div className="flex items-center gap-2">
              <ConfluenceDots count={confluence} total={3} />
              <span className="text-[9px]" style={{ color: COLORS.textMuted }}>
                {confluence}/3
              </span>
            </div>
          </div>
        </div>

        {/* Trade Setup */}
        {signal && direction !== 'WAIT' && (
          <div className="flex-shrink-0" style={{ borderBottom: `1px solid ${COLORS.border}` }}>
            <div
              className="flex items-center px-3 py-1.5"
              style={{ borderBottom: `1px solid ${COLORS.border}`, background: COLORS.surface }}
            >
              <span className="panel-label">Trade Setup</span>
            </div>

            <SetupRow label="Entry" value={formatPrice(signal.entry_low ?? 0)} color={COLORS.text} />
            <SetupRow label="Stop Loss" value={formatPrice(signal.stop_loss ?? 0)} color={COLORS.short} highlight />
            <SetupRow label="Take Profit 1" value={formatPrice(signal.take_profit_1 ?? 0)} color={COLORS.long} highlight />
            <SetupRow label="Take Profit 2" value={formatPrice(signal.take_profit_2 ?? 0)} color={COLORS.long} highlight />

            <div
              className="grid px-2 py-1.5 gap-x-4"
              style={{
                gridTemplateColumns: '1fr 1fr',
                borderBottom: `1px solid ${COLORS.border}`,
                background: COLORS.surface,
              }}
            >
              <div className="flex flex-col">
                <span className="data-label text-[9px]">Leverage</span>
                <span className="data-value text-[12px] font-semibold" style={{ color: COLORS.accent }}>
                  {signal.recommended_leverage ?? 0}x
                </span>
              </div>
              <div className="flex flex-col">
                <span className="data-label text-[9px]">R:R Ratio</span>
                <span className="data-value text-[12px] font-semibold" style={{ color: COLORS.text }}>
                  {(signal.risk_reward_ratio ?? 0).toFixed(2)}
                </span>
              </div>
            </div>

            <SetupRow
              label="Liquidation"
              value={formatPrice(signal.liquidation_price ?? 0)}
              color={COLORS.warn}
              highlight
            />
          </div>
        )}

        {/* Votes */}
        <div className="flex-shrink-0">
          <div
            className="flex items-center px-3 py-1.5"
            style={{ borderBottom: `1px solid ${COLORS.border}`, background: COLORS.surface }}
          >
            <span className="panel-label">Votes</span>
          </div>

          {displayVotes.length === 0 ? (
            <div className="px-3 py-3 text-[10px]" style={{ color: COLORS.textMuted }}>
              Awaiting data...
            </div>
          ) : (
            displayVotes.map((v, i) => (
              <div
                key={i}
                className="flex items-center gap-2 px-3 py-1 row-hover"
                style={{ borderBottom: `1px solid ${COLORS.border}` }}
              >
                <VoteDot vote={v.vote} />
                <span
                  className="flex-1 text-[10px] truncate"
                  style={{ color: COLORS.textSecondary }}
                  title={v.description || v.name}
                >
                  {v.name}
                </span>
                <span
                  className="text-[9px] font-semibold"
                  style={{
                    color: VOTE_COLORS[v.vote] ?? COLORS.neutral,
                    fontFamily: 'IBM Plex Sans, sans-serif',
                    letterSpacing: '0.04em',
                  }}
                >
                  {v.vote}
                </span>
              </div>
            ))
          )}
        </div>

        {/* Warnings */}
        {warnings.length > 0 && (
          <div
            className="flex-shrink-0 mt-auto"
            style={{ borderTop: `1px solid ${COLORS.border}` }}
          >
            <div
              className="flex items-center px-3 py-1.5"
              style={{ borderBottom: `1px solid ${COLORS.border}`, background: COLORS.surface }}
            >
              <span className="panel-label" style={{ color: COLORS.warn }}>Warnings</span>
            </div>
            {warnings.map((w, i) => (
              <div
                key={i}
                className="flex items-start gap-2 px-3 py-1.5 text-[10px]"
                style={{
                  color: COLORS.warn,
                  borderBottom: `1px solid ${COLORS.border}`,
                  background: 'rgba(196,154,60,0.04)',
                }}
              >
                <span style={{ flexShrink: 0, marginTop: 1 }}>⚠</span>
                <span>{w}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
