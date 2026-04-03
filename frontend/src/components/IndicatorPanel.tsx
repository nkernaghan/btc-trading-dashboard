'use client';

import { useState, useMemo } from 'react';
import { useDashboardStore } from '@/stores/dashboard';
import { CATEGORY_LABELS, VOTE_COLORS, COLORS } from '@/lib/constants';
import type { IndicatorVote } from '@/lib/types';

const CATEGORY_ORDER = ['ORDER_FLOW', 'MACRO_DERIVATIVES', 'ON_CHAIN', 'SENTIMENT', 'TECHNICAL', 'VOLATILITY'];

function VoteDot({ vote }: { vote: string }) {
  const color = VOTE_COLORS[vote] ?? COLORS.neutral;
  return (
    <div
      className="vote-dot flex-shrink-0"
      style={{ background: color, boxShadow: vote !== 'NEUTRAL' ? `0 0 4px ${color}60` : undefined }}
    />
  );
}

function StrengthPips({ strength }: { strength: number }) {
  return (
    <div className="flex items-center gap-px ml-1">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="strength-pip"
          style={{
            background: i <= strength
              ? 'var(--text-secondary)'
              : 'var(--border-strong)',
          }}
        />
      ))}
    </div>
  );
}

function CategoryRow({
  cat,
  votes,
  collapsed,
  onToggle,
}: {
  cat: string;
  votes: IndicatorVote[];
  collapsed: boolean;
  onToggle: () => void;
}) {
  const bullCount = votes.filter((v) => v.vote === 'BULL').length;
  const bearCount = votes.filter((v) => v.vote === 'BEAR').length;
  const label = CATEGORY_LABELS[cat] || cat.replace(/_/g, ' ');

  return (
    <div>
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-2 py-1.5 transition-colors duration-75 row-hover"
        style={{
          borderBottom: `1px solid ${COLORS.border}`,
        }}
      >
        <span
          className="text-[9px] font-semibold tracking-widest uppercase"
          style={{ color: COLORS.textMuted, fontFamily: 'IBM Plex Sans, sans-serif' }}
        >
          {label}
        </span>
        <div className="flex items-center gap-1.5">
          {bullCount > 0 && (
            <span className="text-[9px] font-medium" style={{ color: COLORS.long }}>{bullCount}B</span>
          )}
          {bearCount > 0 && (
            <span className="text-[9px] font-medium" style={{ color: COLORS.short }}>{bearCount}S</span>
          )}
          <span style={{ color: COLORS.textMuted, fontSize: 8, marginLeft: 2 }}>
            {collapsed ? '▶' : '▼'}
          </span>
        </div>
      </button>

      {!collapsed && (
        <div>
          {votes.map((ind, i) => (
            <div
              key={i}
              className="flex items-center px-2 py-1 row-hover"
              style={{
                borderBottom: i < votes.length - 1 ? `1px solid ${COLORS.border}` : undefined,
                gap: 6,
              }}
            >
              <VoteDot vote={ind.vote} />
              <span
                className="flex-1 text-[10px] truncate"
                style={{ color: COLORS.textSecondary }}
                title={ind.description || ind.name}
              >
                {ind.name}
              </span>
              <StrengthPips strength={ind.strength ?? 1} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function IndicatorPanel() {
  const { votes } = useDashboardStore();
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const { grouped, bullCount, bearCount, totalCount } = useMemo(() => {
    const map: Record<string, IndicatorVote[]> = {};
    let bull = 0;
    let bear = 0;
    for (const v of votes) {
      const cat = v.category || 'OTHER';
      if (!map[cat]) map[cat] = [];
      map[cat].push(v);
      if (v.vote === 'BULL') bull++;
      if (v.vote === 'BEAR') bear++;
    }
    return { grouped: map, bullCount: bull, bearCount: bear, totalCount: votes.length };
  }, [votes]);

  const categories = CATEGORY_ORDER.filter((c) => grouped[c]).concat(
    Object.keys(grouped).filter((c) => !CATEGORY_ORDER.includes(c))
  );

  return (
    <div
      className="flex flex-col h-full overflow-hidden"
      style={{ background: COLORS.panel }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-2 py-2 flex-shrink-0"
        style={{ borderBottom: `1px solid ${COLORS.border}` }}
      >
        <span className="panel-label">Signals</span>
        {totalCount > 0 && (
          <div className="flex items-center gap-2 text-[9px]">
            <span style={{ color: COLORS.long }}>{bullCount}↑</span>
            <span style={{ color: COLORS.short }}>{bearCount}↓</span>
            <span style={{ color: COLORS.textMuted }}>{totalCount - bullCount - bearCount}=</span>
          </div>
        )}
      </div>

      {/* Summary bar */}
      {totalCount > 0 && (
        <div
          className="flex-shrink-0 px-2 py-1.5 flex items-center gap-2"
          style={{ borderBottom: `1px solid ${COLORS.border}`, background: COLORS.surface }}
        >
          <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: COLORS.border }}>
            <div
              className="h-full rounded-full transition-all duration-300"
              style={{
                width: `${(bullCount / Math.max(totalCount, 1)) * 100}%`,
                background: bullCount > bearCount ? COLORS.long : bearCount > bullCount ? COLORS.short : COLORS.warn,
              }}
            />
          </div>
          <span
            className="text-[9px] font-medium flex-shrink-0 data-value"
            style={{
              color: bullCount > bearCount ? COLORS.long : bearCount > bullCount ? COLORS.short : COLORS.textSecondary,
              fontFamily: 'IBM Plex Sans, sans-serif',
            }}
          >
            {bullCount}/{totalCount}
          </span>
        </div>
      )}

      {/* Indicator list */}
      <div className="flex-1 overflow-y-auto">
        {categories.length === 0 ? (
          <div className="px-2 py-3 text-[10px]" style={{ color: COLORS.textMuted }}>
            Awaiting data...
          </div>
        ) : (
          categories.map((cat) => (
            <CategoryRow
              key={cat}
              cat={cat}
              votes={grouped[cat]}
              collapsed={!!collapsed[cat]}
              onToggle={() => setCollapsed((p) => ({ ...p, [cat]: !p[cat] }))}
            />
          ))
        )}
      </div>
    </div>
  );
}
