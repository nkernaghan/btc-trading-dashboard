'use client';

import { useWebSocket } from '@/hooks/useWebSocket';
import { usePollingData } from '@/hooks/useApi';
import TopBar from '@/components/TopBar';
import IndicatorPanel from '@/components/IndicatorPanel';
import MainChart from '@/components/MainChart';
import BottomCharts from '@/components/BottomCharts';
import SignalPanel from '@/components/SignalPanel';
import PositionTracker from '@/components/PositionTracker';

export default function Dashboard() {
  useWebSocket();
  usePollingData();

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden" style={{ background: '#0c0e13' }}>
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <div className="w-[180px] flex-shrink-0">
          <IndicatorPanel />
        </div>
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-hidden">
            <MainChart />
          </div>
          <div className="h-[130px] flex-shrink-0">
            <BottomCharts />
          </div>
        </div>
        <div className="w-[240px] flex-shrink-0 flex flex-col">
          <div className="flex-1 overflow-hidden">
            <SignalPanel />
          </div>
          <PositionTracker />
        </div>
      </div>
    </div>
  );
}
