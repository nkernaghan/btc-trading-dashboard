'use client';

import { useState, useMemo } from 'react';
import { useDashboardStore } from '@/stores/dashboard';
import { CATEGORY_LABELS, VOTE_COLORS, COLORS } from '@/lib/constants';
import type { IndicatorVote } from '@/lib/types';

export default function IndicatorPanel() {
  const { votes } = useDashboardStore();
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const grouped = useMemo(() => {
    const map: Record<string, IndicatorVote[]> = {};
    for (const v of votes) {
      const cat = v.category || 'OTHER';
      if (!map[cat]) map[cat] = [];
      map[cat].push(v);
    }
    return map;
  }, [votes]);

  const categories = Object.keys(grouped);

  return (
    <div className="flex flex-col h-full overflow-y-auto p-2" style={{ background: COLORS.panel, borderRight: `1px solid ${COLORS.border}` }}>
      <div className="text-[10px] font-medium tracking-widest uppercase mb-2 px-1" style={{ color: COLORS.textMuted, fontFamily: 'IBM Plex Sans, sans-serif' }}>
        Indicators
      </div>

      {categories.length === 0 && (
        <div className="text-[10px] px-1" style={{ color: COLORS.textMuted }}>Awaiting data...</div>
      )}

      {categories.map((cat) => (
        <div key={cat} className="mb-1">
          <button
            onClick={() => setCollapsed(p => ({ ...p, [cat]: !p[cat] }))}
            className="w-full flex items-center justify-between px-1 py-1 text-[10px] transition-colors rounded-sm"
            style={{ color: COLORS.textSecondary }}
            onMouseEnter={e => (e.currentTarget.style.background = COLORS.surface)}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <span className="font-medium tracking-wider uppercase" style={{ fontFamily: 'IBM Plex Sans, sans-serif' }}>
              {CATEGORY_LABELS[cat] || cat.replace(/_/g, ' ')}
            </span>
            <span style={{ color: COLORS.textMuted, fontSize: 9 }}>{collapsed[cat] ? '+' : '\u2013'}</span>
          </button>

          {!collapsed[cat] && (
            <div className="pl-1 pb-1">
              {grouped[cat].map((ind, i) => (
                <div key={i} className="flex items-center justify-between text-[10px] py-px px-1">
                  <span style={{ color: COLORS.textSecondary }}>{ind.name}</span>
                  <span className="font-medium" style={{ color: VOTE_COLORS[ind.vote] || COLORS.neutral }}>
                    {ind.vote}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
