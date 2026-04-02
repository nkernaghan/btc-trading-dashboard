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
    <div className="h-screen w-screen flex flex-col overflow-hidden">
      {/* Top bar */}
      <TopBar />

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Indicator Panel */}
        <div className="w-[200px] flex-shrink-0">
          <IndicatorPanel />
        </div>

        {/* Center: Chart + Bottom */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Main chart */}
          <div className="flex-1 overflow-hidden">
            <MainChart />
          </div>

          {/* Bottom charts strip */}
          <div className="h-[160px] flex-shrink-0">
            <BottomCharts />
          </div>
        </div>

        {/* Right: Signal + Position */}
        <div className="w-[260px] flex-shrink-0 flex flex-col">
          <div className="flex-1 overflow-hidden">
            <SignalPanel />
          </div>
          <PositionTracker />
        </div>
      </div>
    </div>
  );
}
