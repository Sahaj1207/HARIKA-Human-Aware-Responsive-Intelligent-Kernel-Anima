import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

export interface LightsProps {
  intensity?: number;
}

/**
 * Lights — Subtle, Soft Lighting Setup creating visual depth and bloom-like aura.
 */
export const Lights: React.FC<LightsProps> = ({ intensity = 1.0 }) => {
  const coreLightRef = useRef<THREE.PointLight>(null);

  useFrame((state) => {
    if (coreLightRef.current) {
      const t = state.clock.getElapsedTime();
      // Smooth light pulse
      coreLightRef.current.intensity = (3.5 + Math.sin(t * 1.2) * 0.5) * intensity;
    }
  });

  return (
    <>
      {/* Softer ambient lighting */}
      <ambientLight intensity={0.25 * intensity} color="#0b1329" />

      {/* Subtle hemisphere sky/ground contrast */}
      <hemisphereLight
        color="#38bdf8"
        groundColor="#030712"
        intensity={0.45 * intensity}
      />

      {/* Central Core Point Light creating natural glow halo */}
      <pointLight
        ref={coreLightRef}
        position={[0, 0, 0]}
        intensity={3.5 * intensity}
        distance={10}
        color="#38bdf8"
        decay={2}
      />

      {/* Soft rim light for spherical depth highlight */}
      <directionalLight
        position={[4, 6, 4]}
        intensity={0.5 * intensity}
        color="#e0f2fe"
      />
    </>
  );
};
