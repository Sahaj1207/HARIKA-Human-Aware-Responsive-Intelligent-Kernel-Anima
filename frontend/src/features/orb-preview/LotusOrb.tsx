import React, { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { glow, living, useDrive, type OrbState, type Ring } from '@/components/orb/drive';

/** One petal: a slim pointed leaf, cupped across and curving outward to its tip (real 3D geometry).
 * Each vertex carries how far along the petal it is (0 at the heart, 1 at the tip) for its colour. */
export function petalPoint(u: number, v: number, length: number, width: number): [number, number, number] {
  const half = Math.pow(Math.sin(Math.PI * Math.min(v * 1.04, 1)), 0.9) * (1 - 0.45 * v) * width;
  const across = (u - 0.5) * 2;
  const x = across * half;
  const y = v * length;
  const cup = -0.6 * across * across * half;
  const curl = 0.4 * Math.pow(v, 2.4) * length;
  return [x, y, cup + curl];
}

function petalGeometry(length: number, width: number): THREE.BufferGeometry {
  const geometry = new THREE.PlaneGeometry(1, 1, 12, 28);
  const position = geometry.attributes.position as THREE.BufferAttribute;
  const along = new Float32Array(position.count);
  for (let i = 0; i < position.count; i++) {
    const u = position.getX(i) + 0.5;
    const v = position.getY(i) + 0.5;
    position.setXYZ(i, ...petalPoint(u, v, length, width));
    along[i] = v;
  }
  geometry.setAttribute('along', new THREE.BufferAttribute(along, 1));
  geometry.computeVertexNormals();
  return geometry;
}

export const RINGS: Ring[] = [
  { count: 7, length: 0.52, width: 0.2, lift: 0.28, spin: 1, offset: 0 },
  { count: 9, length: 0.72, width: 0.22, lift: 0.7, spin: -1, offset: Math.PI / 9 },
  { count: 11, length: 0.82, width: 0.21, lift: 1.08, spin: 0.7, offset: 0 },
  { count: 13, length: 0.7, width: 0.18, lift: 1.42, spin: -0.5, offset: Math.PI / 13 },
];

/** Petal glass: colour glows from the heart outward to the tips, edges catch the light. */
function petalMaterial(): THREE.MeshPhysicalMaterial {
  const material = new THREE.MeshPhysicalMaterial({
    roughness: 0.22, metalness: 0.05, clearcoat: 1, clearcoatRoughness: 0.08, iridescence: 0.5,
    transparent: true, opacity: 0.86, side: THREE.DoubleSide, depthWrite: false,
  });
  material.userData.uniforms = { base: { value: new THREE.Color() }, tip: { value: new THREE.Color() }, light: { value: 1 } };
  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, material.userData.uniforms);
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nattribute float along;\nvarying float vAlong;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvAlong = along;');
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', '#include <common>\nuniform vec3 base;\nuniform vec3 tip;\nuniform float light;\nvarying float vAlong;')
      .replace('#include <color_fragment>', '#include <color_fragment>\ndiffuseColor.rgb = mix(base, tip, smoothstep(0.0, 1.0, vAlong));')
      .replace('#include <emissivemap_fragment>',
        '#include <emissivemap_fragment>\ntotalEmissiveRadiance = mix(base, tip, vAlong) * light * (1.2 - 0.6 * vAlong);');
  };
  return material;
}

const STAMENS = 24;
const MOTES = 28;

/** The Lotus of Light: glass petals in four rings around a warm heart, breathing, opening and turning. */
export const LotusOrb: React.FC<{ state: OrbState; mood: string; signature?: string; detail?: 'full' | 'small' }> = ({
  state, mood, signature = '', detail = 'full',
}) => {
  const drive = useDrive(state, mood, signature);
  const root = useRef<THREE.Group>(null);
  const rings = useRef<(THREE.Group | null)[]>([]);
  const petals = useRef<THREE.Mesh[][]>([[], [], [], []]);
  const heart = useRef<THREE.Mesh>(null);
  const halo = useRef<THREE.Sprite>(null);
  const aura = useRef<THREE.Sprite>(null);
  const stamens = useRef<THREE.Points>(null);
  const motes = useRef<THREE.Points>(null);
  const shown = useMemo(() => (detail === 'small' ? RINGS.slice(0, 3) : RINGS), [detail]);
  const geometries = useMemo(() => shown.map((r) => petalGeometry(r.length, r.width)), [shown]);
  const materials = useMemo(() => shown.map(() => petalMaterial()), [shown]);
  const tint = useMemo(() => new THREE.Color(), []);
  const tipTint = useMemo(() => new THREE.Color(), []);
  const stamenGeometry = useMemo(() => {
    const positions = new Float32Array(STAMENS * 3);
    for (let i = 0; i < STAMENS; i++) {
      const angle = (i / STAMENS) * Math.PI * 2;
      const r = 0.1 + (i % 2) * 0.04;
      positions.set([Math.cos(angle) * r, 0.16 + (i % 3) * 0.03, Math.sin(angle) * r], i * 3);
    }
    const built = new THREE.BufferGeometry();
    built.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    return built;
  }, []);
  const moteSeeds = useMemo(() => Array.from({ length: MOTES }, () => ({
    angle: Math.random() * Math.PI * 2, radius: 0.15 + Math.random() * 0.55, phase: Math.random(), speed: 0.08 + Math.random() * 0.1,
  })), []);
  const moteGeometry = useMemo(() => {
    const built = new THREE.BufferGeometry();
    built.setAttribute('position', new THREE.BufferAttribute(new Float32Array(MOTES * 3), 3));
    built.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 2);
    return built;
  }, []);

  useFrame(() => {
    const d = drive.current;
    if (!root.current) return;
    // Tilted toward you so you see into the flower; turning slowly; leaning toward the pointer.
    root.current.rotation.x = -0.6 - d.look.y * 0.18;
    root.current.rotation.z = -d.look.x * 0.12;
    root.current.rotation.y = d.t * 0.5;
    root.current.position.y = -0.05 + d.breath * 0.02;

    const light = 0.45 + d.glow * 0.45 + d.shimmer * 0.6 + d.voice * 0.5;
    shown.forEach((ring, r) => {
      const group = rings.current[r];
      if (group) group.rotation.y = ring.spin * d.t * d.swirl * 1.4;
      const uniforms = materials[r].userData.uniforms;
      // Inner rings carry more of the heart's warmth; outer rings fade to the accent at their tips.
      living(d.heart, d.life, tint).lerp(living(d.main, d.life, tipTint), 0.35 + r * 0.18);
      uniforms.base.value.copy(tint);
      uniforms.tip.value.copy(living(r < 2 ? d.main : d.accent, d.life, tipTint));
      uniforms.light.value = light * (1 - r * 0.12);
      petals.current[r].forEach((petal, i) => {
        const ripple = Math.sin(d.clock * 7 + i * 1.3 + r) * d.voice * 0.14;
        petal.rotation.x = ring.lift * (0.72 + d.open * 0.45) + d.breath * 0.035 + ripple;
      });
    });

    if (heart.current) {
      const pulse = 1 + d.voice * 0.35 + d.breath * 0.03 + d.shimmer * 0.15;
      heart.current.scale.setScalar(0.13 * pulse);
      const material = heart.current.material as THREE.MeshStandardMaterial;
      living(d.heart, d.life, material.emissive);
      material.emissiveIntensity = 1.4 + d.glow * 1.2 + d.voice * 1.5;
    }
    if (stamens.current) {
      const material = stamens.current.material as THREE.PointsMaterial;
      living(d.heart, d.life, material.color);
      material.opacity = 0.6 + d.voice * 0.4 + d.shimmer * 0.4;
      stamens.current.rotation.y = -d.t * 0.8;
    }
    if (motes.current) {
      const position = moteGeometry.attributes.position as THREE.BufferAttribute;
      moteSeeds.forEach((seed, i) => {
        const life = (seed.phase + d.clock * seed.speed) % 1;
        const angle = seed.angle + d.t * 0.4;
        position.setXYZ(i, Math.cos(angle) * seed.radius, 0.1 + life * 1.1, Math.sin(angle) * seed.radius);
      });
      position.needsUpdate = true;
      const material = motes.current.material as THREE.PointsMaterial;
      living(d.heart, d.life, material.color);
      material.opacity = 0.25 + d.glow * 0.25 + d.voice * 0.3;
    }
    if (halo.current) {
      halo.current.scale.setScalar(0.8 + d.glow * 0.35 + d.voice * 0.4);
      living(d.heart, d.life, (halo.current.material as THREE.SpriteMaterial).color);
    }
    if (aura.current) {
      aura.current.scale.setScalar(2.7 + d.breath * 0.06 + d.voice * 0.3);
      const material = aura.current.material as THREE.SpriteMaterial;
      living(d.main, d.life, material.color);
      material.opacity = 0.2 * d.glow + d.shimmer * 0.12;
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
                  position={[0, 0, 0.03]}
                />
              </group>
            ))}
          </group>
        ))}
        <mesh ref={heart} position={[0, 0.1, 0]}>
          <sphereGeometry args={[1, 32, 32]} />
          <meshStandardMaterial color="#ffffff" emissive="#ffd27a" emissiveIntensity={2} roughness={0.4} />
        </mesh>
        {detail === 'full' && (
          <points ref={stamens} geometry={stamenGeometry}>
            <pointsMaterial map={glow()} size={0.07} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
          </points>
        )}
        <sprite ref={halo} position={[0, 0.1, 0]}>
          <spriteMaterial map={glow()} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
        </sprite>
      </group>
      {detail === 'full' && (
        <points ref={motes} geometry={moteGeometry} position={[0, -0.4, 0]}>
          <pointsMaterial map={glow()} size={0.05} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
        </points>
      )}
    </group>
  );
};
