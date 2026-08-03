import React from 'react';
import { PerspectiveCamera } from '@react-three/drei';

export const Camera: React.FC = () => {
  return (
    <PerspectiveCamera
      makeDefault
      position={[0, 0, 7]}
      fov={45}
      near={0.1}
      far={1000}
    />
  );
};
