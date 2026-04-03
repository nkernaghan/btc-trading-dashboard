'use client';

import { useState } from 'react';
import { useDashboardStore } from '@/stores/dashboard';
import { formatFunding, formatCompact, formatPct } from '@/lib/format';

const TABS = ['Macro', 'Sentiment', 'Funding', 'Open Interest', 'News'] as const;
type Tab = typeof TABS[number];

export default function BottomCharts() {
  const [activeTab, setActiveTab] = useState<Tab>('Macro');
  const { fundingRate, openInterest, oiDelta, indicators } = useDashboardStore();

  const macro = (indicators as any)?.macro_data as Record<string, { symbol: string; price: number; change_pct: number }> | undefined;
  const fearGreed = (indicators as any)?.sentiment_fear_greed as { value: number; classification: string } | undefined;
  const dominance = (indicators as any)?.sentiment_btc_dominance as { btc_dominance: number } | undefined;
  const news = (indicators as any)?.news_articles as { title: string; source: string; published: string }[] | undefined;
  const coinglass = (indicators as any)?.coinglass_data as any;

  return (
    <div className="flex flex-col h-full bg-[#12122a] border-t border-[#2a2a4a]">
      {/* Tab bar */}
      <div className="flex border-b border-[#2a2a4a]">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-1.5 text-[10px] uppercase tracking-wider transition-colors ${
              activeTab === tab
                ? 'text-[#4488ff] border-b border-[#4488ff]'
                : 'text-[#888] hover:text-[#e0e0e0]'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 p-2 overflow-hidden">

        {activeTab === 'Macro' && (
          <div className="flex gap-4 items-center justify-center h-full">
            {macro ? Object.entries(macro).map(([key, data]) => (
              <div key={key} className="text-center px-3">
                <div className="text-[10px] text-[#888] uppercase">{key}</div>
                <div className="text-sm font-bold text-[#e0e0e0]">
                  {data.price?.toLocaleString(undefined, { maximumFractionDigits: 2 }) ?? '--'}
                </div>
                <div className="text-[10px]" style={{ color: (data.change_pct ?? 0) >= 0 ? '#00ff88' : '#ff4444' }}>
                  {formatPct(data.change_pct)}
                </div>
              </div>
            )) : (
              <div className="text-xs text-[#888]">Loading macro data...</div>
            )}
            {dominance && (
              <div className="text-center px-3 border-l border-[#2a2a4a]">
                <div className="text-[10px] text-[#888] uppercase">BTC.D</div>
                <div className="text-sm font-bold text-[#f7931a]">{dominance.btc_dominance}%</div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'Sentiment' && (
          <div className="flex gap-6 items-center justify-center h-full">
            <div className="text-center">
              <div className="text-[10px] text-[#888] uppercase">Fear & Greed</div>
              <div className="text-3xl font-bold" style={{
                color: fearGreed ? (fearGreed.value <= 25 ? '#ff4444' : fearGreed.value <= 50 ? '#ff8800' : fearGreed.value <= 75 ? '#888' : '#00ff88') : '#888'
              }}>
                {fearGreed?.value ?? '--'}
              </div>
              <div className="text-xs" style={{
                color: fearGreed ? (fearGreed.value <= 25 ? '#ff4444' : fearGreed.value <= 50 ? '#ff8800' : '#888') : '#888'
              }}>
                {fearGreed?.classification ?? '--'}
              </div>
            </div>
            {dominance && (
              <div className="text-center border-l border-[#2a2a4a] pl-6">
                <div className="text-[10px] text-[#888] uppercase">BTC Dominance</div>
                <div className="text-2xl font-bold text-[#f7931a]">{dominance.btc_dominance}%</div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'Funding' && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="text-2xl font-bold" style={{ color: fundingRate >= 0 ? '#00ff88' : '#ff4444' }}>
                {formatFunding(fundingRate)}
              </div>
              <div className="text-xs text-[#888] mt-1">Current Funding Rate</div>
              <div className="text-[10px] text-[#888] mt-2">
                {fundingRate > 0 ? 'Longs paying shorts' : fundingRate < 0 ? 'Shorts paying longs' : 'Neutral'}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'Open Interest' && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="text-2xl font-bold text-[#e0e0e0]">
                {formatCompact(openInterest)}
              </div>
              <div className="text-xs text-[#888] mt-1">Open Interest</div>
              <div className="text-sm mt-2" style={{ color: (oiDelta ?? 0) >= 0 ? '#00ff88' : '#ff4444' }}>
                {(oiDelta ?? 0) >= 0 ? '+' : ''}{(oiDelta ?? 0).toFixed(2)}% 24h
              </div>
            </div>
          </div>
        )}

        {activeTab === 'News' && (
          <div className="h-full overflow-y-auto space-y-1">
            {news && news.length > 0 ? news.slice(0, 8).map((article, i) => (
              <div key={i} className="flex items-start gap-2 text-[10px]">
                <span className="text-[#4488ff] flex-shrink-0">{article.source}</span>
                <span className="text-[#e0e0e0] truncate">{article.title}</span>
              </div>
            )) : (
              <div className="text-xs text-[#888] text-center mt-4">Loading news...</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
