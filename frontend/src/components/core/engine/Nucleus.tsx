import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

export interface NucleusProps {
  state?: string;
}

/**
 * Nucleus — Central Glowing Energy Nucleus for HARIKA AI Core
 * Soft, deep emissive sphere with gentle idle breathing pulse.
 */
export const Nucleus: React.FC<NucleusProps> = () => {
  const meshRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.MeshPhysicalMaterial>(null);

  useFrame((state) => {
    const t = state.clock.getElapsedTime();

    if (meshRef.current) {
      // Gentle breathing pulse
      const scale = 1.0 + Math.sin(t * 1.0) * 0.035;
      meshRef.current.scale.set(scale, scale, scale);

      // Slow rotation
      meshRef.current.rotation.y = t * 0.1;
    }

    if (materialRef.current) {
      // Soft emissive pulse
      materialRef.current.emissiveIntensity = 1.8 + Math.sin(t * 1.2) * 0.35;
    }
  });

  return (
    <mesh ref={meshRef} position={[0, 0, 0]}>
      <sphereGeometry args={[0.85, 64, 64]} />
      <meshPhysicalMaterial
        ref={materialRef}
        color="#38bdf8"
        emissive="#0284c7"
        emissiveIntensity={1.8}
        roughness={0.08}
        metalness={0.1}
        clearcoat={0.8}
        clearcoatRoughness={0.1}
        transmission={0.2}
        thickness={0.8}
      />
    </mesh>
  );
};
