import React from 'react';

export interface CrystalButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'accent' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  icon?: React.ReactNode;
}

export const CrystalButton: React.FC<CrystalButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  icon,
  className = '',
  ...props
}) => {
  const variantStyles = {
    primary: 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500/30 hover:border-cyan-500/60 shadow-lg shadow-cyan-500/10',
    secondary: 'bg-white/5 text-slate-300 border border-white/10 hover:bg-white/10 hover:text-white',
    accent: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/30',
    outline: 'border border-slate-700 text-slate-300 hover:border-slate-500 hover:text-white',
    ghost: 'text-slate-400 hover:text-slate-200 hover:bg-white/5',
    danger: 'bg-rose-500/20 text-rose-300 border border-rose-500/40 hover:bg-rose-500/30',
  };

  const sizeStyles = {
    sm: 'px-2.5 py-1 text-xs space-x-1 rounded-md',
    md: 'px-3.5 py-1.5 text-xs font-medium space-x-1.5 rounded-lg',
    lg: 'px-4 py-2 text-sm font-semibold space-x-2 rounded-xl',
  };

  return (
    <button
      className={`inline-flex items-center justify-center font-mono uppercase tracking-wider transition-all duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      {children && <span>{children}</span>}
    </button>
  );
};
