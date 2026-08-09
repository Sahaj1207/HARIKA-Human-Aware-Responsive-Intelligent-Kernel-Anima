import React, { useState, useEffect } from 'react';
import { diagnosticsRegistry } from './diagnosticsRegistry';
import { performanceMonitor, PerformanceMetrics } from '../performance/performanceMonitor';
import { CrystalCard } from '../components/CrystalCard';
import { CrystalBadge } from '../components/CrystalBadge';
import { Activity, Cpu, HardDrive, Zap, Terminal } from 'lucide-react';

export const DeveloperPanel: React.FC = () => {
  const [metrics, setMetrics] = useState<PerformanceMetrics>(performanceMonitor.getMetrics());
  const cards = diagnosticsRegistry.getCards();

  useEffect(() => {
    const interval = setInterval(() => {
      setMetrics(performanceMonitor.getMetrics());
    }, 500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-4">
      {/* Live Telemetry Performance Dashboard */}
      <div className="space-y-2">
        <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
          <Activity className="w-3.5 h-3.5 text-cyan-400" />
          <span>Live Telemetry Performance Dashboard</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <CrystalCard hoverGlow className="p-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-slate-400 flex items-center space-x-1">
                <Cpu className="w-3 h-3 text-cyan-400" />
                <span>FPS / Render</span>
              </span>
              <CrystalBadge variant="cyan">{metrics.fps} FPS</CrystalBadge>
            </div>
            <div className="text-xs font-mono text-slate-200 mt-1">Renders: {metrics.renderCount}</div>
          </CrystalCard>

          <CrystalCard hoverGlow className="p-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-slate-400 flex items-center space-x-1">
                <HardDrive className="w-3 h-3 text-emerald-400" />
                <span>Memory Heap</span>
              </span>
              <CrystalBadge variant="emerald">{metrics.memoryUsageMb} MB</CrystalBadge>
            </div>
            <div className="text-xs font-mono text-slate-200 mt-1">JS Heap Usage</div>
          </CrystalCard>

          <CrystalCard hoverGlow className="p-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-slate-400 flex items-center space-x-1">
                <Zap className="w-3 h-3 text-amber-400" />
                <span>API Latency</span>
              </span>
              <CrystalBadge variant="amber">{metrics.apiLatencyMs}ms</CrystalBadge>
            </div>
            <div className="text-xs font-mono text-slate-200 mt-1">Streaming: {metrics.streamingLatencyMs}ms</div>
          </CrystalCard>

          <CrystalCard hoverGlow className="p-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-slate-400 flex items-center space-x-1">
                <Terminal className="w-3 h-3 text-sky-400" />
                <span>Voice / Vision</span>
              </span>
              <CrystalBadge variant="cyan">{metrics.voiceLatencyMs}ms</CrystalBadge>
            </div>
            <div className="text-xs font-mono text-slate-200 mt-1">Vision: {metrics.visionLatencyMs}ms</div>
          </CrystalCard>
        </div>
      </div>

      {/* Registered Subsystem Diagnostics Cards */}
      <div className="space-y-2 pt-2 border-t border-white/5">
        <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
          Subsystem Diagnostics Cards ({cards.length})
        </div>
        {cards.length === 0 ? (
          <div className="text-xs font-mono text-slate-500 italic p-3 text-center surface-card rounded-lg border border-white/5">
            No registered subsystem diagnostic cards.
          </div>
        ) : (
          cards.map((c) => (
            <CrystalCard key={c.id} className="p-3 space-y-1">
              <h4 className="text-xs font-mono font-bold text-cyan-300 uppercase">{c.title}</h4>
              <c.component />
            </CrystalCard>
          ))
        )}
      </div>
    </div>
  );
};
