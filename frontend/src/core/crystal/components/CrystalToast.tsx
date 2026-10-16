import React from 'react';
import { X } from 'lucide-react';
import { HarikaOrb } from '@/components/apple/HarikaOrb';

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

/** A notification banner in the style of macOS / iOS notifications. */
export const CrystalToast: React.FC<CrystalToastProps> = ({ toast, onDismiss }) => (
  <div
    role={toast.type === 'error' ? 'alert' : 'status'}
    className="group relative glass rounded-[18px] p-3 pr-9 flex items-start gap-3 bubble-enter"
  >
    <HarikaOrb size={34} state={toast.type === 'error' ? 'error' : 'idle'} />
    <div className="min-w-0">
      <p className="t-callout font-semibold text-label">{toast.title}</p>
      {toast.message && <p className="t-footnote text-label-2 mt-0.5">{toast.message}</p>}
    </div>
    <button
      type="button"
      onClick={() => onDismiss(toast.id)}
      aria-label="Dismiss"
      className="absolute top-2 right-2 w-6 h-6 grid place-items-center rounded-full bg-fill text-label-2 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
    >
      <X className="w-3 h-3" />
    </button>
  </div>
);
