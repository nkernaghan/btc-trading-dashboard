'use client';

import { useState, useEffect } from 'react';
import { useDashboardStore } from '@/stores/dashboard';
import { VOTE_COLORS, COLORS } from '@/lib/constants';
import { formatPrice, formatPct } from '@/lib/format';
import { fetchSignal, loadLastSignal, fetchSignalHistory } from '@/hooks/useApi';
import type { IndicatorVote, Signal } from '@/lib/types';

function VoteDot({ vote }: { vote: string }) {
  const color = VOTE_COLORS[vote] ?? COLORS.neutral;
  return (
    <div style={{ width: 5, height: 5, borderRadius: '50%', background: color, flexShrink: 0, boxShadow: vote !== 'NEUTRAL' ? `0 0 4px ${color}80` : undefined }} />
  );
}

function SetupRow({ label, value, color, highlight }: { label: string; value: string; color: string; highlight?: boolean }) {
  return (
    <div className="flex items-center justify-between px-2 py-1 row-hover" style={{ background: highlight ? `${color}08` : undefined, borderBottom: `1px solid ${COLORS.border}` }}>
      <span className="data-label text-[10px]">{label}</span>
      <span className="data-value text-[11px] font-medium" style={{ color }}>{value}</span>
    </div>
  );
}

// Position sizing calculator
function PositionSizer({ signal }: { signal: Signal }) {
  const recLeverage = signal.recommended_leverage ?? 20;
  const score = signal.composite_score ?? 0;
  const strength = signal.strength ?? 'NONE';

  // Recommended position size ($1-$1000) based on signal confidence
  // STRONG (70-100): $500-$1000 scaled by score
  // WEAK (50-69): $50-$300 scaled by score
  // NONE: $0
  const recCapital = strength === 'NONE' ? 0
    : strength === 'STRONG' ? Math.round(500 + (score - 70) / 30 * 500)
    : Math.round(50 + (score - 50) / 20 * 250);

  const [capital, setCapital] = useState(recCapital);
  const [leverage, setLeverage] = useState(recLeverage);
  const entry = signal.entry_low ?? 0;
  const sl = signal.stop_loss ?? 0;
  const tp1 = signal.take_profit_1 ?? 0;
  const tp2 = signal.take_profit_2 ?? 0;

  // Update when signal changes
  useEffect(() => { setLeverage(recLeverage); setCapital(recCapital); }, [recLeverage, recCapital]);

  const positionSize = capital * leverage;
  const slPct = entry > 0 ? Math.abs(sl - entry) / entry : 0;
  const tp1Pct = entry > 0 ? Math.abs(tp1 - entry) / entry : 0;
  const tp2Pct = entry > 0 ? Math.abs(tp2 - entry) / entry : 0;
  const liqPrice = signal.direction === 'LONG'
    ? entry * (1 - 1 / leverage)
    : entry * (1 + 1 / leverage);

  const slLoss = -(capital * slPct * leverage);
  const tp1Win = capital * tp1Pct * leverage;
  const tp2Win = capital * tp2Pct * leverage;
  const slReturnPct = -slPct * leverage * 100;
  const tp1ReturnPct = tp1Pct * leverage * 100;
  const tp2ReturnPct = tp2Pct * leverage * 100;

  const inputStyle = {
    background: COLORS.base,
    border: `1px solid ${COLORS.border}`,
    color: COLORS.text,
    outline: 'none',
  };

  return (
    <div style={{ borderBottom: `1px solid ${COLORS.border}` }}>
      <div className="flex items-center px-2 py-1.5" style={{ borderBottom: `1px solid ${COLORS.border}`, background: COLORS.surface }}>
        <span className="panel-label">Position Sizing</span>
      </div>
      <div className="px-2 py-2">
        {/* Recommended badge */}
        <div className="flex items-center justify-between mb-2 px-1.5 py-1 rounded" style={{ background: `${COLORS.accent}08`, border: `1px solid ${COLORS.accent}20` }}>
          <div className="flex items-center gap-1.5 text-[9px]" style={{ color: COLORS.textMuted }}>
            <span>Rec:</span>
            <span className="font-semibold" style={{ color: COLORS.accent }}>${recCapital}</span>
            <span>@</span>
            <span className="font-semibold" style={{ color: COLORS.accent }}>{recLeverage}x</span>
          </div>
          {(leverage !== recLeverage || capital !== recCapital) && (
            <button
              onClick={() => { setLeverage(recLeverage); setCapital(recCapital); }}
              className="px-1.5 py-px rounded text-[8px] font-medium"
              style={{ background: COLORS.accent, color: '#fff', cursor: 'pointer', border: 'none' }}
            >
              Use Rec
            </button>
          )}
        </div>

        {/* Capital + Leverage inputs */}
        <div className="flex items-center gap-2 mb-1.5">
          <div className="flex items-center gap-1">
            <span className="text-[10px]" style={{ color: COLORS.textSecondary }}>$</span>
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(Math.max(1, Math.min(100000, Number(e.target.value) || 0)))}
              className="data-value text-[11px] font-medium px-1.5 py-0.5 rounded"
              style={{ width: 65, ...inputStyle }}
            />
          </div>
          <span className="text-[10px]" style={{ color: COLORS.textMuted }}>×</span>
          <div className="flex items-center gap-1">
            <input
              type="number"
              value={leverage}
              onChange={(e) => setLeverage(Math.max(1, Math.min(150, Number(e.target.value) || 1)))}
              className="data-value text-[11px] font-medium px-1.5 py-0.5 rounded"
              style={{ width: 45, ...inputStyle }}
            />
            <span className="text-[10px]" style={{ color: COLORS.textSecondary }}>x</span>
          </div>
        </div>

        {/* Position size + liq */}
        <div className="flex items-center justify-between mb-2 text-[10px]">
          <span style={{ color: COLORS.textSecondary }}>Position: <span className="data-value font-medium" style={{ color: COLORS.text }}>${positionSize.toLocaleString()}</span></span>
          <span style={{ color: COLORS.textSecondary }}>Liq: <span className="data-value font-medium" style={{ color: COLORS.warn }}>{formatPrice(liqPrice)}</span></span>
        </div>

        {/* Leverage slider */}
        <input
          type="range"
          min={1}
          max={100}
          value={leverage}
          onChange={(e) => setLeverage(Number(e.target.value))}
          className="w-full mb-2"
          style={{ height: 4, accentColor: COLORS.accent }}
        />

        {/* Projected PnL */}
        <div className="space-y-1 text-[10px]">
          <div className="flex justify-between items-center px-1.5 py-1 rounded" style={{ background: 'rgba(239,83,80,0.06)' }}>
            <span style={{ color: COLORS.textSecondary }}>SL hit</span>
            <div className="flex items-center gap-2">
              <span className="data-value" style={{ color: COLORS.short }}>{slReturnPct.toFixed(1)}%</span>
              <span className="data-value font-semibold" style={{ color: COLORS.short }}>${slLoss.toFixed(2)}</span>
            </div>
          </div>
          <div className="flex justify-between items-center px-1.5 py-1 rounded" style={{ background: 'rgba(38,166,154,0.06)' }}>
            <span style={{ color: COLORS.textSecondary }}>TP1 hit</span>
            <div className="flex items-center gap-2">
              <span className="data-value" style={{ color: COLORS.long }}>+{tp1ReturnPct.toFixed(1)}%</span>
              <span className="data-value font-semibold" style={{ color: COLORS.long }}>+${tp1Win.toFixed(2)}</span>
            </div>
          </div>
          <div className="flex justify-between items-center px-1.5 py-1 rounded" style={{ background: 'rgba(38,166,154,0.06)' }}>
            <span style={{ color: COLORS.textSecondary }}>TP2 hit</span>
            <div className="flex items-center gap-2">
              <span className="data-value" style={{ color: COLORS.long }}>+{tp2ReturnPct.toFixed(1)}%</span>
              <span className="data-value font-semibold" style={{ color: COLORS.long }}>+${tp2Win.toFixed(2)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Signal history with PnL
function SignalHistory() {
  const [history, setHistory] = useState<any[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const { price } = useDashboardStore();

  useEffect(() => {
    if (showHistory) {
      fetchSignalHistory(20).then(setHistory);
    }
  }, [showHistory]);

  if (!showHistory) {
    return (
      <div style={{ borderBottom: `1px solid ${COLORS.border}` }}>
        <button
          onClick={() => setShowHistory(true)}
          className="w-full px-3 py-1.5 text-[10px] font-medium text-left row-hover"
          style={{ color: COLORS.accent, fontFamily: 'Inter, sans-serif' }}
        >
          View Signal History →
        </button>
      </div>
    );
  }

  return (
    <div style={{ borderBottom: `1px solid ${COLORS.border}` }}>
      <div className="flex items-center justify-between px-2 py-1.5" style={{ borderBottom: `1px solid ${COLORS.border}`, background: COLORS.surface }}>
        <span className="panel-label">History</span>
        <button onClick={() => setShowHistory(false)} className="text-[10px]" style={{ color: COLORS.textMuted }}>×</button>
      </div>
      <div className="max-h-[200px] overflow-y-auto">
        {history.length === 0 ? (
          <div className="px-3 py-2 text-[10px]" style={{ color: COLORS.textMuted }}>No history yet</div>
        ) : (
          history.map((h, i) => {
            const entry = h.entry_low ?? 0;
            const sl = h.stop_loss ?? 0;
            const tp1 = h.take_profit_1 ?? 0;
            const isLong = h.direction === 'LONG';
            const currentPnlPct = entry > 0
              ? (isLong ? (price - entry) / entry : (entry - price) / entry) * 100
              : 0;
            const dirColor = h.direction === 'LONG' ? COLORS.long : h.direction === 'SHORT' ? COLORS.short : COLORS.neutral;
            const pnlColor = currentPnlPct >= 0 ? COLORS.long : COLORS.short;

            return (
              <div key={i} className="flex items-center gap-2 px-2 py-1.5 row-hover text-[10px]" style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                <span className="font-semibold" style={{ color: dirColor, width: 40 }}>{h.direction}</span>
                <span className="data-value" style={{ color: COLORS.textSecondary, width: 35 }}>{(h.composite_score ?? 0).toFixed(0)}%</span>
                <span className="data-value" style={{ color: COLORS.textSecondary }}>{formatPrice(entry)}</span>
                <span className="data-value font-semibold ml-auto" style={{ color: pnlColor }}>
                  {currentPnlPct >= 0 ? '+' : ''}{currentPnlPct.toFixed(2)}%
                </span>
                <span className="text-[9px]" style={{ color: COLORS.textMuted }}>
                  {h.timestamp ? new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export default function SignalPanel() {
  const { signal, votes, warnings, price } = useDashboardStore();
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  // Load signal once on mount
  useEffect(() => {
    loadLastSignal().then(() => setLastRefresh(new Date()));
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchSignal();
    setLastRefresh(new Date());
    setRefreshing(false);
  };

  const direction = signal?.direction ?? 'WAIT';
  const score = signal?.composite_score ?? 0;
  const strength = signal?.strength ?? 'NONE';
  const confluence = signal?.confluence_count ?? 0;
  const dirColor = direction === 'LONG' ? COLORS.long : direction === 'SHORT' ? COLORS.short : COLORS.neutral;
  const dirBg = direction === 'LONG' ? 'rgba(38,166,154,0.05)' : direction === 'SHORT' ? 'rgba(239,83,80,0.05)' : 'transparent';
  const glowClass = direction === 'LONG' ? 'score-glow-long' : direction === 'SHORT' ? 'score-glow-short' : '';
  const displayVotes: IndicatorVote[] = votes.length > 0 ? votes : (signal?.votes ?? []);
  const bullVotes = displayVotes.filter((v) => v.vote === 'BULL').length;
  const bearVotes = displayVotes.filter((v) => v.vote === 'BEAR').length;

  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ background: COLORS.panel }}>
      {/* Header with refresh button */}
      <div className="flex items-center justify-between px-3 py-2 flex-shrink-0" style={{ borderBottom: `1px solid ${COLORS.border}` }}>
        <div className="flex items-center gap-2">
          <span className="panel-label">Signal</span>
          <span className="text-[9px]" style={{ color: COLORS.textMuted }}>
            {lastRefresh ? lastRefresh.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''}
          </span>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="px-2 py-0.5 text-[10px] font-semibold rounded transition-colors"
          style={{
            background: refreshing ? COLORS.surface : COLORS.accent,
            color: refreshing ? COLORS.textMuted : '#fff',
            border: 'none',
            cursor: refreshing ? 'wait' : 'pointer',
            fontFamily: 'Inter, sans-serif',
          }}
        >
          {refreshing ? '...' : '↻ Refresh'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Score Block */}
        <div className={`flex flex-col items-center justify-center py-4 ${glowClass}`} style={{ background: dirBg, borderBottom: `1px solid ${COLORS.border}` }}>
          <div className="text-[9px] font-semibold tracking-widest uppercase mb-1.5 px-2 py-0.5 rounded-sm" style={{ color: dirColor, background: `${dirColor}15`, fontFamily: 'Inter, sans-serif' }}>
            {direction}
          </div>
          <div className="data-value font-semibold" style={{ fontSize: 34, lineHeight: 1, color: dirColor, textShadow: direction !== 'WAIT' ? `0 0 20px ${dirColor}40` : undefined }}>
            {score > 0 ? score.toFixed(1) : '--'}
          </div>
          <div className="flex items-center gap-2 mt-2 text-[9px]" style={{ color: COLORS.textMuted }}>
            {strength !== 'NONE' && <span className="font-semibold" style={{ color: strength === 'STRONG' ? dirColor : COLORS.textMuted }}>{strength}</span>}
            <span>{bullVotes}↑ {bearVotes}↓</span>
            <span>{confluence}/3 TF</span>
          </div>
        </div>

        {/* Trade Setup */}
        {signal && direction !== 'WAIT' && (
          <>
            <div style={{ borderBottom: `1px solid ${COLORS.border}` }}>
              <div className="flex items-center px-2 py-1.5" style={{ borderBottom: `1px solid ${COLORS.border}`, background: COLORS.surface }}>
                <span className="panel-label">Trade Setup</span>
              </div>
              <SetupRow label="Entry" value={formatPrice(signal.entry_low ?? 0)} color={COLORS.text} />
              <SetupRow label="Stop Loss" value={formatPrice(signal.stop_loss ?? 0)} color={COLORS.short} highlight />
              <SetupRow label="TP1" value={formatPrice(signal.take_profit_1 ?? 0)} color={COLORS.long} highlight />
              <SetupRow label="TP2" value={formatPrice(signal.take_profit_2 ?? 0)} color={COLORS.long} highlight />
              <div className="grid px-2 py-1.5 gap-x-4" style={{ gridTemplateColumns: '1fr 1fr', borderBottom: `1px solid ${COLORS.border}`, background: COLORS.surface }}>
                <div className="flex flex-col">
                  <span className="data-label text-[9px]">Leverage</span>
                  <span className="data-value text-[12px] font-semibold" style={{ color: COLORS.accent }}>{signal.recommended_leverage ?? 0}x</span>
                </div>
                <div className="flex flex-col">
                  <span className="data-label text-[9px]">R:R</span>
                  <span className="data-value text-[12px] font-semibold" style={{ color: COLORS.text }}>{(signal.risk_reward_ratio ?? 0).toFixed(2)}</span>
                </div>
              </div>
              <SetupRow label="Liquidation" value={formatPrice(signal.liquidation_price ?? 0)} color={COLORS.warn} highlight />
            </div>

            {/* Position Sizing */}
            <PositionSizer signal={signal} />
          </>
        )}

        {/* Signal History */}
        <SignalHistory />

        {/* Votes */}
        <div className="flex-shrink-0">
          <div className="flex items-center px-2 py-1.5" style={{ borderBottom: `1px solid ${COLORS.border}`, background: COLORS.surface }}>
            <span className="panel-label">Votes</span>
          </div>
          {displayVotes.length === 0 ? (
            <div className="px-3 py-2 text-[10px]" style={{ color: COLORS.textMuted }}>Click Refresh to load signal</div>
          ) : (
            displayVotes.map((v, i) => (
              <div key={i} className="flex items-center gap-2 px-2 py-1 row-hover" style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                <VoteDot vote={v.vote} />
                <span className="flex-1 text-[10px] truncate" style={{ color: COLORS.textSecondary }}>{v.name}</span>
                <span className="text-[9px] font-semibold" style={{ color: VOTE_COLORS[v.vote] ?? COLORS.neutral }}>{v.vote}</span>
              </div>
            ))
          )}
        </div>

        {/* Warnings */}
        {warnings.length > 0 && (
          <div>
            {warnings.map((w, i) => (
              <div key={i} className="flex items-start gap-2 px-2 py-1 text-[10px]" style={{ color: COLORS.warn, borderBottom: `1px solid ${COLORS.border}`, background: 'rgba(255,152,0,0.04)' }}>
                <span>⚠</span><span>{w}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
