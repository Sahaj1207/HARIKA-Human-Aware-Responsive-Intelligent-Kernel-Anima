import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { CoreState } from '@/types';

export interface NucleusProps {
  state?: CoreState;
}

/**
 * Nucleus — 3D Central Energy Core Mesh
 * Dynamic GPU-accelerated interpolation reacting to CoreState via R3F useFrame at 60 FPS.
 */
export const Nucleus: React.FC<NucleusProps> = ({ state = 'idle' }) => {
  const meshRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.MeshPhysicalMaterial>(null);

  useFrame((r3fState) => {
    const t = r3fState.clock.getElapsedTime();

    if (!meshRef.current || !materialRef.current) return;

    // State-driven dynamic target parameters
    let targetScale = 1.0;
    let targetRotationSpeed = 0.1;
    let targetEmissiveIntensity = 1.8;
    let targetColor = new THREE.Color('#38bdf8'); // Sky Cyan
    let targetEmissive = new THREE.Color('#0284c7');

    switch (state) {
      case 'thinking':
        targetScale = 1.05 + Math.sin(t * 3.5) * 0.06;
        targetRotationSpeed = 0.6;
        targetEmissiveIntensity = 2.4;
        targetColor = new THREE.Color('#818cf8'); // Indigo
        targetEmissive = new THREE.Color('#4f46e5');
        break;
      case 'speaking':
        targetScale = 1.03 + Math.sin(t * 4.5) * 0.05;
        targetRotationSpeed = 0.3;
        targetEmissiveIntensity = 2.2;
        targetColor = new THREE.Color('#22d3ee'); // Bright Cyan
        targetEmissive = new THREE.Color('#0891b2');
        break;
      case 'listening':
        targetScale = 1.04 + Math.sin(t * 2.0) * 0.04;
        targetRotationSpeed = 0.25;
        targetEmissiveIntensity = 2.1;
        targetColor = new THREE.Color('#38bdf8'); // Cyan
        targetEmissive = new THREE.Color('#0284c7');
        break;
      case 'error':
        targetScale = 0.98 + Math.sin(t * 1.5) * 0.02;
        targetRotationSpeed = 0.05;
        targetEmissiveIntensity = 1.2;
        targetColor = new THREE.Color('#f87171'); // Soft Red
        targetEmissive = new THREE.Color('#991b1b');
        break;
      case 'booting':
        targetScale = 0.9 + Math.sin(t * 1.0) * 0.08;
        targetRotationSpeed = 0.2;
        targetEmissiveIntensity = 1.4;
        targetColor = new THREE.Color('#a855f7');
        break;
      case 'idle':
      default:
        targetScale = 1.0 + Math.sin(t * 1.0) * 0.035;
        targetRotationSpeed = 0.1;
        targetEmissiveIntensity = 1.8;
        targetColor = new THREE.Color('#38bdf8');
        targetEmissive = new THREE.Color('#0284c7');
        break;
    }

    // Apply scale & rotation interpolations
    meshRef.current.scale.set(targetScale, targetScale, targetScale);
    meshRef.current.rotation.y += targetRotationSpeed * 0.015;

    // Smooth material color & emissive interpolation (300-500ms lerp)
    materialRef.current.color.lerp(targetColor, 0.08);
    materialRef.current.emissive.lerp(targetEmissive, 0.08);
    materialRef.current.emissiveIntensity = THREE.MathUtils.lerp(
      materialRef.current.emissiveIntensity,
      targetEmissiveIntensity,
      0.08
    );
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
