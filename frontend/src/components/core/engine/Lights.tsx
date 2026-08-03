import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { CoreState } from '@/types';

export interface LightsProps {
  intensity?: number;
  state?: CoreState;
}

export const Lights: React.FC<LightsProps> = ({ intensity = 1.0, state = 'idle' }) => {
  const coreLightRef = useRef<THREE.PointLight>(null);

  useFrame((r3fState) => {
    if (!coreLightRef.current) return;
    const t = r3fState.clock.getElapsedTime();

    let targetIntensity = 3.5;
    let targetColor = new THREE.Color('#38bdf8');

    if (state === 'thinking') {
      targetIntensity = 5.0 + Math.sin(t * 4) * 0.8;
      targetColor = new THREE.Color('#818cf8');
    } else if (state === 'speaking') {
      targetIntensity = 4.2 + Math.sin(t * 5) * 0.6;
      targetColor = new THREE.Color('#22d3ee');
    } else if (state === 'error') {
      targetIntensity = 2.0 + Math.sin(t * 2) * 0.4;
      targetColor = new THREE.Color('#f87171');
    } else {
      targetIntensity = (3.5 + Math.sin(t * 1.2) * 0.5) * intensity;
      targetColor = new THREE.Color('#38bdf8');
    }

    coreLightRef.current.intensity = THREE.MathUtils.lerp(
      coreLightRef.current.intensity,
      targetIntensity,
      0.08
    );
    coreLightRef.current.color.lerp(targetColor, 0.08);
  });

  return (
    <>
      <ambientLight intensity={0.25 * intensity} color="#0b1329" />
      <hemisphereLight
        color="#38bdf8"
        groundColor="#030712"
        intensity={0.45 * intensity}
      />
      <pointLight
        ref={coreLightRef}
        position={[0, 0, 0]}
        intensity={3.5 * intensity}
        distance={10}
        color="#38bdf8"
        decay={2}
      />
      <directionalLight
        position={[4, 6, 4]}
        intensity={0.5 * intensity}
        color="#e0f2fe"
      />
    </>
  );
};
