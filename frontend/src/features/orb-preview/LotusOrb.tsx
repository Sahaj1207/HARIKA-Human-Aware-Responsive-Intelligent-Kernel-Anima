import React, { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { glow, living, useDrive, type OrbState } from './drive';

/** One petal: a leaf shape, cupped across and curving outward toward its tip (real 3D geometry). */
function petalGeometry(length: number, width: number): THREE.BufferGeometry {
  const geometry = new THREE.PlaneGeometry(1, 1, 10, 24);
  const position = geometry.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < position.count; i++) {
    const u = position.getX(i) + 0.5; // 0..1 across
    const v = position.getY(i) + 0.5; // 0..1 base to tip
    const half = Math.pow(Math.sin(Math.PI * Math.min(v * 1.08, 1)), 0.75) * (1 - 0.35 * v) * width;
    const x = (u - 0.5) * 2 * half;
    const y = v * length;
    const cup = -0.55 * Math.pow((u - 0.5) * 2, 2) * half; // edges rise: a cupped petal
    const curl = 0.35 * Math.pow(v, 2.2) * length; // the tip bends outward
    position.setXYZ(i, x, y, cup + curl);
  }
  geometry.computeVertexNormals();
  return geometry;
}

interface Ring {
  count: number;
  length: number;
  width: number;
  lift: number; // base tilt away from upright
  spin: number; // direction when thinking
  offset: number;
}

const WHITE = new THREE.Color('#ffffff');

const RINGS: Ring[] = [
  { count: 6, length: 0.62, width: 0.34, lift: 0.35, spin: 1, offset: 0 },
  { count: 8, length: 0.82, width: 0.36, lift: 0.85, spin: -1, offset: Math.PI / 8 },
  { count: 8, length: 0.7, width: 0.32, lift: 1.25, spin: 0.6, offset: 0 },
];

/** The Lotus of Light: glass petals in three rings around a warm heart, breathing, opening and turning. */
export const LotusOrb: React.FC<{ state: OrbState; mood: string; detail?: 'full' | 'small' }> = ({ state, mood, detail = 'full' }) => {
  const drive = useDrive(state, mood);
  const root = useRef<THREE.Group>(null);
  const rings = useRef<(THREE.Group | null)[]>([]);
  const petals = useRef<THREE.Mesh[][]>([[], [], []]);
  const heart = useRef<THREE.Mesh>(null);
  const halo = useRef<THREE.Sprite>(null);
  const aura = useRef<THREE.Sprite>(null);
  const shown = useMemo(() => (detail === 'small' ? RINGS.slice(0, 2) : RINGS), [detail]);
  const geometries = useMemo(() => shown.map((r) => petalGeometry(r.length, r.width)), [shown]);
  const materials = useMemo(
    () => shown.map(() => new THREE.MeshPhysicalMaterial({
      color: '#ffffff', emissive: '#ffffff', emissiveIntensity: 0.35, roughness: 0.18, metalness: 0.05,
      clearcoat: 1, clearcoatRoughness: 0.1, sheen: 1, sheenColor: new THREE.Color('#ffffff'), iridescence: 0.6,
      transparent: true, opacity: 0.82, side: THREE.DoubleSide, depthWrite: false,
    })),
    [shown],
  );
  const tint = useMemo(() => new THREE.Color(), []);

  useFrame(() => {
    const d = drive.current;
    if (!root.current) return;
    // Tilted toward you so you see into the flower; turning slowly; leaning toward the pointer.
    root.current.rotation.x = -0.55 - d.look.y * 0.18;
    root.current.rotation.z = -d.look.x * 0.12;
    root.current.rotation.y = d.t * 0.6;
    root.current.position.y = -0.18 + d.breath * 0.02;

    shown.forEach((ring, r) => {
      const group = rings.current[r];
      if (group) group.rotation.y = ring.spin * d.t * d.swirl * 1.4;
      const material = materials[r];
      living(r === 0 ? d.heart : r === 1 ? d.main : d.accent, d.life, tint);
      material.color.copy(tint).lerp(WHITE, 0.35);
      material.emissive.copy(tint);
      material.emissiveIntensity = 0.28 + d.glow * 0.3 + d.shimmer * 0.5 + d.voice * 0.35;
      petals.current[r].forEach((petal, i) => {
        // Opening toward you when listening, breathing at rest, rippling with her voice.
        const ripple = Math.sin(d.clock * 7 + i * 1.3 + r) * d.voice * 0.16;
        petal.rotation.x = ring.lift * (0.75 + d.open * 0.45) + d.breath * 0.04 + ripple;
      });
    });

    if (heart.current) {
      const pulse = 1 + d.voice * 0.35 + d.breath * 0.03 + d.shimmer * 0.15;
      heart.current.scale.setScalar(0.17 * pulse);
      const material = heart.current.material as THREE.MeshStandardMaterial;
      living(d.heart, d.life, material.emissive);
      material.emissiveIntensity = 1.2 + d.glow * 1.2 + d.voice * 1.5;
    }
    if (halo.current) {
      halo.current.scale.setScalar(0.9 + d.glow * 0.35 + d.voice * 0.4);
      living(d.heart, d.life, (halo.current.material as THREE.SpriteMaterial).color);
    }
    if (aura.current) {
      aura.current.scale.setScalar(2.6 + d.breath * 0.06 + d.voice * 0.3);
      const material = aura.current.material as THREE.SpriteMaterial;
      living(d.main, d.life, material.color);
      material.opacity = 0.22 * d.glow + d.shimmer * 0.12;
    }
  });

  return (
    <group>
      <sprite ref={aura} renderOrder={-1}>
        <spriteMaterial map={glow()} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
      </sprite>
      <group ref={root}>
        {shown.map((ring, r) => (
          <group key={r} ref={(g) => { rings.current[r] = g; }}>
            {Array.from({ length: ring.count }, (_, i) => (
              <group key={i} rotation={[0, ring.offset + (i / ring.count) * Math.PI * 2, 0]}>
                <mesh
                  ref={(m) => { if (m) petals.current[r][i] = m; }}
                  geometry={geometries[r]}
                  material={materials[r]}
                  position={[0, 0, 0.04]}
                />
              </group>
            ))}
          </group>
        ))}
        <mesh ref={heart} position={[0, 0.12, 0]}>
          <sphereGeometry args={[1, 32, 32]} />
          <meshStandardMaterial color="#ffffff" emissive="#ffd27a" emissiveIntensity={2} roughness={0.4} />
        </mesh>
        <sprite ref={halo} position={[0, 0.12, 0]}>
          <spriteMaterial map={glow()} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
        </sprite>
      </group>
    </group>
  );
};
