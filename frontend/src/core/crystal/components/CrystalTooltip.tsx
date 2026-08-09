import React, { useState } from 'react';

export interface CrystalTooltipProps {
  content: string;
  children: React.ReactNode;
}

export const CrystalTooltip: React.FC<CrystalTooltipProps> = ({ content, children }) => {
  const [show, setShow] = useState(false);

  return (
    <div className="relative inline-block" onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <div className="absolute bottom-full mb-1.5 left-1/2 -translate-x-1/2 px-2 py-1 bg-slate-900 border border-white/10 rounded-md text-[10px] font-mono text-slate-200 whitespace-nowrap z-50 pointer-events-none shadow-xl animate-in fade-in duration-150">
          {content}
        </div>
      )}
    </div>
  );
};
