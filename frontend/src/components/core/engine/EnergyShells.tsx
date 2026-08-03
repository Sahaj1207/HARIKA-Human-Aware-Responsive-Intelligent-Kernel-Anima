import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { CoreState } from '@/types';

export interface EnergyShellsProps {
  state?: CoreState;
}

export const EnergyShells: React.FC<EnergyShellsProps> = ({ state = 'idle' }) => {
  const outerShellRef = useRef<THREE.Mesh>(null);
  const innerShellRef = useRef<THREE.Mesh>(null);

  useFrame((r3fState) => {
    const t = r3fState.clock.getElapsedTime();

    if (!innerShellRef.current || !outerShellRef.current) return;

    let innerSpeed = 0.06;
    let outerSpeed = -0.04;

    if (state === 'thinking') {
      innerSpeed = 0.25;
      outerSpeed = -0.18;
    } else if (state === 'speaking') {
      innerSpeed = 0.15;
      outerSpeed = -0.1;
    } else if (state === 'listening') {
      innerSpeed = 0.12;
      outerSpeed = -0.08;
    }

    innerShellRef.current.rotation.y += innerSpeed * 0.02;
    innerShellRef.current.rotation.x = Math.sin(t * 0.5) * 0.08;

    outerShellRef.current.rotation.y += outerSpeed * 0.02;
    outerShellRef.current.rotation.z = Math.cos(t * 0.4) * 0.06;
  });

  return (
    <group position={[0, 0, 0]}>
      {/* Inner Translucent Energy Layer */}
      <mesh ref={innerShellRef}>
        <sphereGeometry args={[1.25, 64, 64]} />
        <meshPhysicalMaterial
          color="#38bdf8"
          transmission={0.88}
          opacity={0.5}
          transparent
          roughness={0.1}
          metalness={0.1}
          ior={1.35}
          thickness={0.6}
          specularIntensity={0.9}
        />
      </mesh>

      {/* Outer Subtle Atmosphere Layer */}
      <mesh ref={outerShellRef}>
        <sphereGeometry args={[1.65, 64, 64]} />
        <meshPhysicalMaterial
          color="#6366f1"
          transmission={0.94}
          opacity={0.25}
          transparent
          roughness={0.08}
          metalness={0.05}
          ior={1.15}
          thickness={0.3}
          specularIntensity={0.6}
        />
      </mesh>
    </group>
  );
};
