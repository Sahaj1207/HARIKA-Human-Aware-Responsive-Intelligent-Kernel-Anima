import React from 'react';
import { Canvas } from '@react-three/fiber';
import { Float } from '@react-three/drei';
import { Camera } from './Camera';
import { Lights } from './Lights';
import { Nucleus } from './Nucleus';
import { EnergyShells } from './EnergyShells';
import { CoreState } from '@/types';

export interface CoreCanvasProps {
  state?: CoreState;
  intensity?: number;
}

/**
 * CoreCanvas — Three.js WebGL Rendering Engine for HARIKA AI Core.
 */
export const CoreCanvas: React.FC<CoreCanvasProps> = ({
  state = 'idle',
  intensity = 1.0,
}) => {
  return (
    <div className="w-full h-full relative select-none">
      <Canvas
        gl={{
          antialias: true,
          alpha: true,
          powerPreference: 'high-performance',
        }}
        className="w-full h-full"
      >
        <Camera />
        <Lights intensity={intensity} />

        {/* Slow, Elegant Floating Motion */}
        <Float
          speed={1.0}
          rotationIntensity={0.12}
          floatIntensity={0.25}
          floatingRange={[-0.12, 0.12]}
        >
          <group position={[0, 0, 0]}>
            <Nucleus state={state} />
            <EnergyShells />
          </group>
        </Float>
      </Canvas>
    </div>
  );
};
