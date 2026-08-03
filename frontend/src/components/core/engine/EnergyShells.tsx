import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

/**
 * EnergyShells — Concentric Translucent Energy Layers for HARIKA AI Core
 * Replaced wireframe with two smooth MeshPhysicalMaterial energy shells.
 */
export const EnergyShells: React.FC = () => {
  const outerShellRef = useRef<THREE.Mesh>(null);
  const innerShellRef = useRef<THREE.Mesh>(null);

  // Smooth, slow idle rotation
  useFrame((state) => {
    const t = state.clock.getElapsedTime();

    if (innerShellRef.current) {
      innerShellRef.current.rotation.y = t * 0.06;
      innerShellRef.current.rotation.x = Math.sin(t * 0.04) * 0.08;
    }

    if (outerShellRef.current) {
      outerShellRef.current.rotation.y = -t * 0.04;
      outerShellRef.current.rotation.z = Math.cos(t * 0.03) * 0.06;
    }
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

      {/* Outer Subtle Translucent Atmosphere Layer */}
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
