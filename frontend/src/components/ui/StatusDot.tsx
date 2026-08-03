import React from 'react';

interface StatusDotProps {
  status?: 'active' | 'inactive' | 'warning' | 'error';
  pulse?: boolean;
}

export const StatusDot: React.FC<StatusDotProps> = ({ status = 'active', pulse = true }) => {
  const colors = {
    active: 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]',
    inactive: 'bg-slate-600',
    warning: 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)]',
    error: 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.6)]',
  };

  return (
    <span
      className={`w-2 h-2 rounded-full inline-block ${colors[status]} ${
        pulse ? 'animate-pulse' : ''
      }`}
    />
  );
};
