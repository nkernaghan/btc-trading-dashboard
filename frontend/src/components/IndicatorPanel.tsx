'use client';

import { useState } from 'react';
import { useDashboardStore } from '@/stores/dashboard';
import { CATEGORY_LABELS, VOTE_COLORS } from '@/lib/constants';

export default function IndicatorPanel() {
  const { indicators } = useDashboardStore();
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const toggle = (cat: string) =>
    setCollapsed((prev) => ({ ...prev, [cat]: !prev[cat] }));

  const categories = Object.keys(indicators);

  return (
    <div className="flex flex-col h-full overflow-y-auto bg-[#12122a] border-r border-[#2a2a4a] p-2">
      <h2 className="text-xs text-[#888] uppercase tracking-wider mb-2 px-1">Indicators</h2>

      {categories.length === 0 && (
        <div className="text-xs text-[#888] px-1">Waiting for data...</div>
      )}

      {categories.map((cat) => (
        <div key={cat} className="mb-1">
          <button
            onClick={() => toggle(cat)}
            className="w-full flex items-center justify-between px-1 py-1 text-xs text-[#888] hover:text-[#e0e0e0] transition-colors"
          >
            <span className="uppercase tracking-wider">
              {CATEGORY_LABELS[cat] || cat}
            </span>
            <span>{collapsed[cat] ? '+' : '-'}</span>
          </button>

          {!collapsed[cat] && (
            <div className="space-y-0.5 pl-1">
              {indicators[cat].map((ind, i) => (
                <div key={i} className="flex items-center gap-1.5 text-[10px]">
                  <span
                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: VOTE_COLORS[ind.vote] }}
                  />
                  <span className="text-[#888] truncate flex-1">{ind.name}</span>
                  <span className="text-[#e0e0e0] flex-shrink-0">
                    {typeof ind.value === 'number' ? ind.value.toFixed(2) : (ind.value ?? '--')}
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
