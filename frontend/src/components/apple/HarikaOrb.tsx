import React, { Suspense, lazy, useState } from 'react';
import type { CoreState } from '@/types';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { useOrbLook } from '@/components/orb/appearance';
import type { OrbState } from '@/components/orb/drive';

const OrbCanvas = lazy(() => import('@/components/orb/OrbCanvas'));

interface HarikaOrbProps {
  state?: CoreState;
  size?: number;
  className?: string;
}

const LABELS: Partial<Record<CoreState, string>> = {
  thinking: 'HARIKA is thinking',
  listening: 'HARIKA is listening',
  speaking: 'HARIKA is answering',
  error: 'HARIKA hit a problem',
};

function canDraw3D(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl'));
  } catch {
    return false;
  }
}

const HAS_3D = typeof document !== 'undefined' && canDraw3D();

function prefersStillness(): boolean {
  return document.documentElement.classList.contains('reduced-motion')
    || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

/** The flat orb: colour fields drifting inside a sphere. Shown while the 3D orb loads, and wherever it can't run. */
const FlatOrb: React.FC<{ state: string; mood: string; size: number; className: string; label: string }> = ({
  state, mood, size, className, label,
}) => (
  <div className={`harika-orb shrink-0 ${className}`} data-state={state} data-mood={mood} style={{ width: size, height: size }}
       role="img" aria-label={label}>
    <span />
    <span />
    <span />
    <span />
    <i />
  </div>
);

/** HARIKA's presence. A living 3D Starlit Lotus or Constellation (Settings > General > Appearance) that
 * follows her state and mood; the flat orb while it loads, or where 3D or motion isn't wanted. */
export const HarikaOrb: React.FC<HarikaOrbProps> = ({ state = 'idle', size = 96, className = '' }) => {
  const visualState = (state === 'booting' || state === 'sleeping' ? 'idle' : state) as OrbState;
  const mood = useHARIKAStore((s) => s.mood);
  const look = useOrbLook();
  const [lost, setLost] = useState(false);
  const label = LABELS[state] ?? 'HARIKA';
  const flat = <FlatOrb state={visualState} mood={mood} size={size} className={className} label={label} />;
  if (!HAS_3D || lost || prefersStillness()) return flat;
  return (
    <div className={`shrink-0 ${className}`} style={{ width: size, height: size }} role="img" aria-label={label}>
      <Suspense fallback={flat}>
        <OrbCanvas state={visualState} mood={mood} look={look} size={size} onLost={() => setLost(true)} />
      </Suspense>
    </div>
  );
};
