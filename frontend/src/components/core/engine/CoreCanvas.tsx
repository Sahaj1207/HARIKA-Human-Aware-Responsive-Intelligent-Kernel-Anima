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
        <Lights intensity={intensity} state={state} />

        <Float
          speed={state === 'thinking' ? 2.5 : 1.0}
          rotationIntensity={state === 'thinking' ? 0.35 : 0.12}
          floatIntensity={state === 'thinking' ? 0.45 : 0.25}
          floatingRange={[-0.12, 0.12]}
        >
          <group position={[0, 0, 0]}>
            <Nucleus state={state} />
            <EnergyShells state={state} />
          </group>
        </Float>
      </Canvas>
    </div>
  );
};
