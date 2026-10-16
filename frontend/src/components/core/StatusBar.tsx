import React, { useEffect } from 'react';
import { SlidersHorizontal, Activity } from 'lucide-react';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { healthService } from '@/services/api/health';

export const StatusBar: React.FC = () => {
  const { coreState, isOnline, setIsOnline, toggleQuickPanel, activity } = useHARIKAStore();

  useEffect(() => {
    // Check backend FastAPI server status
    healthService
      .checkHealth()
      .then(() => setIsOnline(true))
      .catch(() => setIsOnline(false));
  }, [setIsOnline]);

  return (
    <header className="w-full px-6 py-4 flex items-center justify-between pointer-events-auto">
      {/* System Brand Title */}
      <div className="flex items-center space-x-3">
        <span className="font-heading text-sm tracking-widest text-slate-200 uppercase font-semibold">
          HARIKA
        </span>
        <span className="text-[10px] font-mono tracking-widest text-slate-500 uppercase">
          v0.1.0-alpha
        </span>
      </div>

      {/* Center Core Mode Indicator */}
      <div className="hidden sm:flex items-center space-x-2 text-xs font-mono text-slate-400">
        <Activity className="w-3.5 h-3.5 text-cyan-500 animate-pulse" />
        <span className="uppercase text-[11px] tracking-wider">
          {activity ? activity : `Mode: ${coreState}`}
        </span>
      </div>

      {/* Right Telemetry Dot & Quick Panel Trigger */}
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2">
          <span
            className={`w-2 h-2 rounded-full ${
              isOnline
                ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]'
                : 'bg-amber-500/70'
            }`}
          />
          <span className="text-[11px] font-mono text-slate-400 uppercase">
            {isOnline ? 'Core Linked' : 'Offline Mode'}
          </span>
        </div>

        <button
          onClick={toggleQuickPanel}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 surface-translucent-subtle transition-colors"
          title="Open System Controls"
        >
          <SlidersHorizontal className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};
