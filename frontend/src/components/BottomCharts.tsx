'use client';

import { useState } from 'react';
import { useDashboardStore } from '@/stores/dashboard';
import { formatFunding, formatCompact, formatPct } from '@/lib/format';
import { COLORS } from '@/lib/constants';

const TABS = ['Macro', 'Sentiment', 'Funding', 'OI', 'News'] as const;
type Tab = typeof TABS[number];

export default function BottomCharts() {
  const [activeTab, setActiveTab] = useState<Tab>('Macro');
  const { fundingRate, openInterest, oiDelta, indicators } = useDashboardStore();

  const macro = (indicators as any)?.macro_data as Record<string, { price: number; change_pct: number }> | undefined;
  const fearGreed = (indicators as any)?.sentiment_fear_greed as { value: number; classification: string } | undefined;
  const dominance = (indicators as any)?.sentiment_btc_dominance as { btc_dominance: number } | undefined;
  const news = (indicators as any)?.news_articles as { title: string; source: string }[] | undefined;

  return (
    <div className="flex flex-col h-full" style={{ background: COLORS.panel, borderTop: `1px solid ${COLORS.border}` }}>
      <div className="flex" style={{ borderBottom: `1px solid ${COLORS.border}` }}>
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className="px-3 py-1 text-[10px] font-medium tracking-wider transition-colors"
            style={{
              color: activeTab === tab ? COLORS.accent : COLORS.textMuted,
              borderBottom: activeTab === tab ? `1px solid ${COLORS.accent}` : '1px solid transparent',
              fontFamily: 'IBM Plex Sans, sans-serif',
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="flex-1 px-3 py-2 overflow-hidden">
        {activeTab === 'Macro' && (
          <div className="flex gap-6 items-center h-full">
            {macro ? Object.entries(macro).map(([key, data]) => (
              <div key={key} className="text-center">
                <div className="text-[9px] tracking-wider uppercase" style={{ color: COLORS.textMuted, fontFamily: 'IBM Plex Sans, sans-serif' }}>{key}</div>
                <div className="text-[13px] font-medium" style={{ color: COLORS.text, fontVariantNumeric: 'tabular-nums' }}>
                  {data.price?.toLocaleString(undefined, { maximumFractionDigits: 2 }) ?? '--'}
                </div>
                <div className="text-[10px]" style={{ color: (data.change_pct ?? 0) >= 0 ? COLORS.long : COLORS.short, fontVariantNumeric: 'tabular-nums' }}>
                  {formatPct(data.change_pct)}
                </div>
              </div>
            )) : <div className="text-[10px]" style={{ color: COLORS.textMuted }}>Loading...</div>}
            {dominance && (
              <div className="text-center pl-4" style={{ borderLeft: `1px solid ${COLORS.border}` }}>
                <div className="text-[9px] tracking-wider uppercase" style={{ color: COLORS.textMuted, fontFamily: 'IBM Plex Sans, sans-serif' }}>BTC.D</div>
                <div className="text-[13px] font-medium" style={{ color: COLORS.btc }}>{dominance.btc_dominance}%</div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'Sentiment' && (
          <div className="flex gap-8 items-center h-full">
            <div className="text-center">
              <div className="text-[9px] tracking-wider uppercase" style={{ color: COLORS.textMuted, fontFamily: 'IBM Plex Sans, sans-serif' }}>Fear & Greed</div>
              <div className="text-[24px] font-semibold" style={{
                color: fearGreed ? (fearGreed.value <= 25 ? COLORS.short : fearGreed.value <= 50 ? COLORS.warn : COLORS.long) : COLORS.neutral,
                fontVariantNumeric: 'tabular-nums',
              }}>
                {fearGreed?.value ?? '--'}
              </div>
              <div className="text-[10px]" style={{ color: COLORS.textSecondary }}>{fearGreed?.classification ?? '--'}</div>
            </div>
            {dominance && (
              <div className="text-center pl-6" style={{ borderLeft: `1px solid ${COLORS.border}` }}>
                <div className="text-[9px] tracking-wider uppercase" style={{ color: COLORS.textMuted, fontFamily: 'IBM Plex Sans, sans-serif' }}>BTC Dominance</div>
                <div className="text-[20px] font-medium" style={{ color: COLORS.btc }}>{dominance.btc_dominance}%</div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'Funding' && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="text-[20px] font-medium" style={{ color: (fundingRate ?? 0) >= 0 ? COLORS.long : COLORS.short, fontVariantNumeric: 'tabular-nums' }}>
                {formatFunding(fundingRate)}
              </div>
              <div className="text-[10px] mt-1" style={{ color: COLORS.textMuted }}>
                {(fundingRate ?? 0) > 0 ? 'Longs paying shorts' : (fundingRate ?? 0) < 0 ? 'Shorts paying longs' : 'Neutral'}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'OI' && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="text-[20px] font-medium" style={{ color: COLORS.text, fontVariantNumeric: 'tabular-nums' }}>
                {formatCompact(openInterest)}
              </div>
              <div className="text-[10px] mt-1" style={{ color: (oiDelta ?? 0) >= 0 ? COLORS.long : COLORS.short }}>
                {formatPct(oiDelta)} 24h
              </div>
            </div>
          </div>
        )}

        {activeTab === 'News' && (
          <div className="h-full overflow-y-auto space-y-1">
            {news?.slice(0, 6).map((a, i) => (
              <div key={i} className="flex items-baseline gap-2 text-[10px] py-0.5">
                <span className="flex-shrink-0 font-medium" style={{ color: COLORS.accent }}>{a.source}</span>
                <span className="truncate" style={{ color: COLORS.textSecondary }}>{a.title}</span>
              </div>
            )) ?? <div className="text-[10px]" style={{ color: COLORS.textMuted }}>Loading...</div>}
          </div>
        )}
      </div>
    </div>
  );
}
