'use client';

import { useState, useCallback } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { usePollingData } from '@/hooks/useApi';
import TopBar from '@/components/TopBar';
import IndicatorPanel from '@/components/IndicatorPanel';
import MainChart from '@/components/MainChart';
import BottomCharts from '@/components/BottomCharts';
import SignalPanel from '@/components/SignalPanel';
import PositionTracker from '@/components/PositionTracker';
import ResizeHandle from '@/components/ResizeHandle';

const LEFT_DEFAULT = 220;
const LEFT_MIN = 150;
const LEFT_MAX = 400;

const RIGHT_DEFAULT = 280;
const RIGHT_MIN = 200;
const RIGHT_MAX = 450;

const BOTTOM_DEFAULT = 148;
const BOTTOM_MIN = 80;
const BOTTOM_MAX = 400;

export default function Dashboard() {
  useWebSocket();
  usePollingData();

  const [leftWidth, setLeftWidth] = useState(LEFT_DEFAULT);
  const [rightWidth, setRightWidth] = useState(RIGHT_DEFAULT);
  const [bottomHeight, setBottomHeight] = useState(BOTTOM_DEFAULT);

  const resizeLeft = useCallback((delta: number) => {
    setLeftWidth((w) => Math.min(LEFT_MAX, Math.max(LEFT_MIN, w + delta)));
  }, []);

  const resizeRight = useCallback((delta: number) => {
    setRightWidth((w) => Math.min(RIGHT_MAX, Math.max(RIGHT_MIN, w - delta)));
  }, []);

  const resizeBottom = useCallback((delta: number) => {
    setBottomHeight((h) => Math.min(BOTTOM_MAX, Math.max(BOTTOM_MIN, h - delta)));
  }, []);

  return (
    <div className="terminal-root">
      <TopBar />
      <div className="terminal-body">
        {/* Left: Indicator Panel */}
        <div className="terminal-left" style={{ width: leftWidth }}>
          <IndicatorPanel />
        </div>

        <ResizeHandle direction="col" onResize={resizeLeft} />

        {/* Center: Chart + Bottom Strip */}
        <div className="terminal-center">
          <div className="terminal-chart">
            <MainChart />
          </div>
          <ResizeHandle direction="row" onResize={resizeBottom} />
          <div className="terminal-bottom" style={{ height: bottomHeight }}>
            <BottomCharts />
          </div>
        </div>

        <ResizeHandle direction="col" onResize={resizeRight} />

        {/* Right: Signal + Position */}
        <div className="terminal-right" style={{ width: rightWidth }}>
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
