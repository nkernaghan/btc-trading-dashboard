'use client';

import { useState } from 'react';
import { useDashboardStore } from '@/stores/dashboard';
import { formatFunding, formatCompact } from '@/lib/format';

const TABS = ['Funding Rate', 'Open Interest', 'Liquidations', 'Correlations', 'ETF Flows'] as const;
type Tab = typeof TABS[number];

export default function BottomCharts() {
  const [activeTab, setActiveTab] = useState<Tab>('Funding Rate');
  const { fundingRate, openInterest, oiDelta } = useDashboardStore();

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
      <div className="flex-1 p-3 overflow-hidden">
        {activeTab === 'Funding Rate' && (
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
                ${formatCompact(openInterest)}
              </div>
              <div className="text-xs text-[#888] mt-1">Open Interest</div>
              <div className="text-sm mt-2" style={{ color: oiDelta >= 0 ? '#00ff88' : '#ff4444' }}>
                {oiDelta >= 0 ? '+' : ''}{(oiDelta ?? 0).toFixed(2)}% 24h
              </div>
            </div>
          </div>
        )}

        {activeTab === 'Liquidations' && (
          <div className="flex items-center justify-center h-full text-xs text-[#888]">
            Liquidation heatmap — awaiting data feed
          </div>
        )}

        {activeTab === 'Correlations' && (
          <div className="flex items-center justify-center h-full text-xs text-[#888]">
            BTC vs ETH / SPX / DXY / Gold correlations — awaiting data feed
          </div>
        )}

        {activeTab === 'ETF Flows' && (
          <div className="flex items-center justify-center h-full text-xs text-[#888]">
            Spot BTC ETF daily flows — awaiting data feed
          </div>
        )}
      </div>
    </div>
  );
}
