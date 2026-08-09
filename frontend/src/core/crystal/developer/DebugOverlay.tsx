import React, { useState, useEffect } from 'react';
import { performanceMonitor, PerformanceMetrics } from '../performance/performanceMonitor';

export interface DebugOverlayProps {
  visible: boolean;
}

export const DebugOverlay: React.FC<DebugOverlayProps> = ({ visible }) => {
  const [metrics, setMetrics] = useState<PerformanceMetrics>(performanceMonitor.getMetrics());

  useEffect(() => {
    if (!visible) return;
    const interval = setInterval(() => {
      setMetrics(performanceMonitor.getMetrics());
    }, 500);
    return () => clearInterval(interval);
  }, [visible]);

  if (!visible) return null;

  return (
    <div className="fixed top-3 left-3 z-50 pointer-events-none bg-slate-950/85 border border-cyan-500/30 backdrop-blur-md rounded-lg p-2.5 shadow-2xl font-mono text-[10px] text-cyan-300 space-y-1">
      <div className="font-bold text-white flex items-center space-x-1">
        <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping inline-block" />
        <span>HARIKA Crystal Core Telemetry</span>
      </div>
      <div className="flex justify-between space-x-4">
        <span>FPS: {metrics.fps}</span>
        <span>Heap: {metrics.memoryUsageMb}MB</span>
      </div>
      <div className="flex justify-between space-x-4 text-slate-300">
        <span>API: {metrics.apiLatencyMs}ms</span>
        <span>Voice: {metrics.voiceLatencyMs}ms</span>
      </div>
    </div>
  );
};
