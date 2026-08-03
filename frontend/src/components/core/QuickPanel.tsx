import React from 'react';
import { X, Moon, Power, Cpu } from 'lucide-react';
import { useHARIKAStore } from '@/store/useHARIKAStore';

export const QuickPanel: React.FC = () => {
  const { isQuickPanelOpen, toggleQuickPanel, coreState, setCoreState } = useHARIKAStore();

  if (!isQuickPanelOpen) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/40 backdrop-blur-xs transition-opacity duration-300">
      <div className="w-80 h-full surface-translucent border-l border-white/10 p-6 flex flex-col justify-between shadow-2xl animate-in slide-in-from-right duration-300">
        <div className="space-y-6">
          <div className="flex items-center justify-between border-b border-white/5 pb-4">
            <div className="flex items-center space-x-2">
              <Cpu className="w-4 h-4 text-cyan-400" />
              <span className="font-heading text-sm text-slate-200 uppercase tracking-wider font-medium">
                System Controls
              </span>
            </div>
            <button
              onClick={toggleQuickPanel}
              className="text-slate-400 hover:text-slate-200 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="space-y-4">
            <div className="text-xs font-mono text-slate-500 uppercase tracking-wider">
              Core Visual State
            </div>
            <div className="grid grid-cols-2 gap-2">
              {(['idle', 'listening', 'processing', 'speaking', 'sleeping'] as const).map(
                (state) => (
                  <button
                    key={state}
                    onClick={() => setCoreState(state)}
                    className={`px-3 py-2 rounded-lg text-xs font-mono uppercase tracking-wider border transition-all ${
                      coreState === state
                        ? 'border-cyan-500/50 bg-cyan-500/10 text-cyan-300'
                        : 'border-white/5 bg-white/5 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {state}
                  </button>
                )
              )}
            </div>
          </div>
        </div>

        <div className="border-t border-white/5 pt-4 flex items-center justify-between text-xs font-mono text-slate-500">
          <button
            onClick={() => setCoreState(coreState === 'sleeping' ? 'idle' : 'sleeping')}
            className="flex items-center space-x-2 text-slate-400 hover:text-slate-200 transition-colors"
          >
            <Moon className="w-4 h-4" />
            <span>{coreState === 'sleeping' ? 'Wake Core' : 'Sleep Core'}</span>
          </button>
          <div className="flex items-center space-x-1">
            <Power className="w-3.5 h-3.5 text-emerald-400" />
            <span>Nominal</span>
          </div>
        </div>
      </div>
    </div>
  );
};
