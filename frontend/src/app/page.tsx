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
    <div className="terminal-root">
      <TopBar />
      <div className="terminal-body">
        {/* Left: Indicator Panel */}
        <div className="terminal-left">
          <IndicatorPanel />
        </div>

        {/* Center: Chart + Bottom Strip */}
        <div className="terminal-center">
          <div className="terminal-chart">
            <MainChart />
          </div>
          <div className="terminal-bottom">
            <BottomCharts />
          </div>
        </div>

        {/* Right: Signal + Position */}
        <div className="terminal-right">
          <div className="terminal-signal">
            <SignalPanel />
          </div>
          <div className="terminal-position">
            <PositionTracker />
          </div>
        </div>
      </div>
    </div>
  );
}
