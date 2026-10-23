import React from 'react';
import type { CoreState } from '@/types';
import { useHARIKAStore } from '@/store/useHARIKAStore';

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

/** HARIKA's presence: color fields drifting inside a glass sphere. Speed and glow follow her state; colors follow her mood. */
export const HarikaOrb: React.FC<HarikaOrbProps> = ({ state = 'idle', size = 96, className = '' }) => {
  const visualState = state === 'booting' || state === 'sleeping' ? 'idle' : state;
  const mood = useHARIKAStore((s) => s.mood);
  return (
    <div
      className={`harika-orb shrink-0 ${className}`}
      data-state={visualState}
      data-mood={mood}
      style={{ width: size, height: size }}
      role="img"
      aria-label={LABELS[state] ?? 'HARIKA'}
    >
      <span />
      <span />
      <span />
      <span />
      <i />
    </div>
  );
};
