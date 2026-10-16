import React, { useEffect } from 'react';
import { Settings } from 'lucide-react';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { healthService } from '@/services/api/health';
import { HarikaOrb } from '@/components/apple/HarikaOrb';

const isMac = typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform);

/** Window toolbar: HARIKA's name and what she's doing right now, like a Messages header. */
export const StatusBar: React.FC<{ onOpenSettings: () => void }> = ({ onOpenSettings }) => {
  const { coreState, isOnline, setIsOnline, activity } = useHARIKAStore();

  useEffect(() => {
    const check = () =>
      healthService
        .checkHealth()
        .then(() => setIsOnline(true))
        .catch(() => setIsOnline(false));
    check();
    const timer = setInterval(check, 10000);
    return () => clearInterval(timer);
  }, [setIsOnline]);

  const status = !isOnline
    ? "Can't reach HARIKA's engine"
    : activity
    ? activity
    : coreState === 'thinking'
    ? 'Thinking…'
    : coreState === 'listening'
    ? 'Listening…'
    : null;

  return (
    <header
      data-tauri-drag-region
      className={`relative z-20 h-[52px] shrink-0 flex items-center justify-center border-b border-separator bg-canvas/80 backdrop-blur-xl ${
        isMac ? 'pl-20' : ''
      }`}
    >
      <div className="flex items-center gap-2.5 pointer-events-none" data-tauri-drag-region>
        <HarikaOrb state={isOnline ? coreState : 'error'} size={22} />
        <div className="leading-tight">
          <p className="t-headline">HARIKA</p>
          {status && <p className={`t-caption ${isOnline ? 'text-label-2' : 'text-danger'}`}>{status}</p>}
        </div>
      </div>
      <button
        type="button"
        onClick={onOpenSettings}
        aria-label="Settings"
        title="Settings"
        className="absolute right-3 w-8 h-8 grid place-items-center rounded-lg text-label-2 hover:text-label hover:bg-fill transition-colors"
      >
        <Settings className="w-[18px] h-[18px]" />
      </button>
    </header>
  );
};
