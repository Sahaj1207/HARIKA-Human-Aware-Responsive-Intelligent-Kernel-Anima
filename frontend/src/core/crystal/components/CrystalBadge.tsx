import React from 'react';

export interface CrystalBadgeProps {
  variant?: 'cyan' | 'emerald' | 'amber' | 'rose' | 'slate';
  children: React.ReactNode;
}

export const CrystalBadge: React.FC<CrystalBadgeProps> = ({
  variant = 'cyan',
  children,
}) => {
  const styles = {
    cyan: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
    emerald: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    amber: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    rose: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
    slate: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
  };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[9px] font-mono font-bold uppercase border tracking-wider ${styles[variant]}`}>
      {children}
    </span>
  );
};
