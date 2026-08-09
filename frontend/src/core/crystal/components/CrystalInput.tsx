import React from 'react';

export interface CrystalInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  icon?: React.ReactNode;
  error?: string;
}

export const CrystalInput: React.FC<CrystalInputProps> = ({
  label,
  icon,
  error,
  className = '',
  ...props
}) => {
  return (
    <div className="space-y-1 w-full">
      {label && <label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{label}</label>}
      <div className="relative flex items-center">
        {icon && <span className="absolute left-3 text-slate-400 pointer-events-none">{icon}</span>}
        <input
          className={`w-full bg-slate-950/80 border border-white/10 rounded-xl py-2 text-xs font-mono text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/30 transition-all ${
            icon ? 'pl-9 pr-3' : 'px-3'
          } ${error ? 'border-rose-500/50 focus:border-rose-500' : ''} ${className}`}
          {...props}
        />
      </div>
      {error && <p className="text-[10px] font-mono text-rose-400">{error}</p>}
    </div>
  );
};
