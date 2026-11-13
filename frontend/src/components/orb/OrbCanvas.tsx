import React, { useEffect } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { ConstellationOrb } from './ConstellationOrb';
import { StarLotusOrb } from './StarLotusOrb';
import type { OrbLook } from './appearance';
import type { OrbState } from './drive';

const SMALL = 48; // at or below this size the orb uses its lighter version

/** Small orbs (the header) redraw at about 30 frames a second: smooth enough, half the work. */
const HalfRate: React.FC = () => {
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => {
    const timer = setInterval(() => invalidate(), 33);
    return () => clearInterval(timer);
  }, [invalidate]);
  return null;
};

/** HARIKA's orb in real 3D: the chosen design, colours and mood, following her state. Loaded on demand. */
const OrbCanvas: React.FC<{ state: OrbState; mood: string; look: OrbLook; size: number; onLost: () => void }> = ({
  state, mood, look, size, onLost,
}) => {
  const small = size <= SMALL;
  const detail = small ? 'small' : 'full';
  const shownMood = look.followMood ? mood : 'warm';
  return (
    <Canvas
      dpr={[1, 2]}
      frameloop={small ? 'demand' : 'always'}
      camera={{ position: [0, 0, 3.1], fov: 40 }}
      gl={{ antialias: !small, alpha: true, powerPreference: 'low-power' }}
      style={{ width: size, height: size }}
      onCreated={({ gl }) => gl.domElement.addEventListener('webglcontextlost', onLost)}
    >
      {small && <HalfRate />}
      {look.style === 'constellation'
        ? <ConstellationOrb state={state} mood={shownMood} signature={look.colours} detail={detail} />
        : <StarLotusOrb state={state} mood={shownMood} signature={look.colours} detail={detail} />}
    </Canvas>
  );
};

export default OrbCanvas;
