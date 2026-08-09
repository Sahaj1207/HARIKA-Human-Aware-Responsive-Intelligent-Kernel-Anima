import React from 'react';

export interface CrystalCardProps extends React.HTMLAttributes<HTMLDivElement> {
  glass?: boolean;
  hoverGlow?: boolean;
}

export const CrystalCard: React.FC<CrystalCardProps> = ({
  children,
  glass = true,
  hoverGlow = false,
  className = '',
  ...props
}) => {
  return (
    <div
      className={`rounded-xl border border-white/10 p-4 transition-all duration-200 ${
        glass ? 'bg-slate-900/60 backdrop-blur-md' : 'bg-slate-900'
      } ${hoverGlow ? 'hover:border-cyan-500/40 hover:shadow-lg hover:shadow-cyan-500/10' : ''} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};
