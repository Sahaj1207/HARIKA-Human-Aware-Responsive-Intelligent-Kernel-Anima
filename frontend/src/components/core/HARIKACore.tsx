import React from 'react';
import { CoreState } from '@/types';
import { CoreCanvas } from './engine/CoreCanvas';

export interface HARIKACoreProps {
  state?: CoreState;
  size?: number; // Base size in px (defaults to 390, ~22% larger)
  intensity?: number; // Ambient light intensity 0-1
}

/**
 * HARIKACore — Independent AI Core Rendering Engine Wrapper
 * Receives strictly 'state' input and renders the refined 3D AI Core engine.
 */
export const HARIKACore: React.FC<HARIKACoreProps> = ({
  state = 'idle',
  size = 390,
  intensity = 1.0,
}) => {
  return (
    <div
      className="relative flex items-center justify-center select-none"
      style={{ width: `${size}px`, height: `${size}px` }}
    >
      {/* 3D WebGL Engine Canvas */}
      <CoreCanvas state={state} intensity={intensity} />

      {/* Minimal Core Status Mode Label */}
      <div className="absolute -bottom-7 text-[11px] font-mono tracking-widest uppercase text-slate-400/80">
        {state}
      </div>
    </div>
  );
};
