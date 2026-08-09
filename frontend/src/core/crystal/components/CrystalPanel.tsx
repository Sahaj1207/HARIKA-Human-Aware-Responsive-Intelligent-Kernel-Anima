import React from 'react';
import { X } from 'lucide-react';

export interface CrystalPanelProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  width?: string;
}

export const CrystalPanel: React.FC<CrystalPanelProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  icon,
  children,
  width = 'w-96',
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-xs transition-opacity duration-300">
      <div className={`${width} h-full bg-slate-950/90 border-l border-white/10 p-6 flex flex-col justify-between shadow-2xl animate-in slide-in-from-right duration-300`}>
        <div className="space-y-4 overflow-y-auto pr-1">
          {/* Panel Header */}
          <div className="flex items-center justify-between border-b border-white/10 pb-4">
            <div className="flex items-center space-x-2">
              {icon && <span className="text-cyan-400">{icon}</span>}
              <div>
                <h3 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-100">{title}</h3>
                {subtitle && <p className="text-[10px] font-mono text-slate-400">{subtitle}</p>}
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Panel Body */}
          <div className="py-2">{children}</div>
        </div>
      </div>
    </div>
  );
};
