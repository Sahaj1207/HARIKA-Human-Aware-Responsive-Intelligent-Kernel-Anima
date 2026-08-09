import React from 'react';
import { CheckCircle, AlertTriangle, AlertCircle, Info, X } from 'lucide-react';

export interface ToastItem {
  id: string;
  type: 'success' | 'warning' | 'error' | 'info';
  title: string;
  message?: string;
}

export interface CrystalToastProps {
  toast: ToastItem;
  onDismiss: (id: string) => void;
}

export const CrystalToast: React.FC<CrystalToastProps> = ({ toast, onDismiss }) => {
  const icons = {
    success: <CheckCircle className="w-4 h-4 text-emerald-400" />,
    warning: <AlertTriangle className="w-4 h-4 text-amber-400" />,
    error: <AlertCircle className="w-4 h-4 text-rose-400" />,
    info: <Info className="w-4 h-4 text-cyan-400" />,
  };

  const borders = {
    success: 'border-emerald-500/40 bg-emerald-950/80 text-emerald-200',
    warning: 'border-amber-500/40 bg-amber-950/80 text-amber-200',
    error: 'border-rose-500/40 bg-rose-950/80 text-rose-200',
    info: 'border-cyan-500/40 bg-cyan-950/80 text-cyan-200',
  };

  return (
    <div className={`flex items-start justify-between space-x-3 p-3.5 rounded-xl border backdrop-blur-md shadow-2xl animate-in slide-in-from-bottom duration-200 ${borders[toast.type]}`}>
      <div className="flex items-start space-x-2.5">
        <span className="mt-0.5 shrink-0">{icons[toast.type]}</span>
        <div>
          <h4 className="text-xs font-mono font-bold uppercase tracking-wider">{toast.title}</h4>
          {toast.message && <p className="text-[11px] font-mono text-slate-300 mt-0.5">{toast.message}</p>}
        </div>
      </div>
      <button
        onClick={() => onDismiss(toast.id)}
        className="p-0.5 rounded text-slate-400 hover:text-white transition-colors"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};
