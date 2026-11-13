import React, { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { glow, living, useDrive, type OrbState } from './drive';

const NOISE = /* glsl */ `
  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
  }
  float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p *= 2.03; a *= 0.5; } return v; }
`;

/** Clear glass: a bright rim where you look across it, a highlight, and faint etched lines that turn with it. */
const glassShader = {
  uniforms: { rim: { value: new THREE.Color() }, opacity: { value: 1 }, time: { value: 0 } },
  vertexShader: /* glsl */ `
    varying vec3 vNormal; varying vec3 vView; varying vec3 vLocal;
    void main() {
      vLocal = position;
      vec4 mv = modelViewMatrix * vec4(position, 1.0);
      vNormal = normalize(normalMatrix * normal);
      vView = normalize(-mv.xyz);
      gl_Position = projectionMatrix * mv;
    }`,
  fragmentShader: /* glsl */ `
    uniform vec3 rim; uniform float opacity; uniform float time;
    varying vec3 vNormal; varying vec3 vView; varying vec3 vLocal;
    void main() {
      vec3 n = normalize(vNormal);
      float facing = max(dot(n, vView), 0.0);
      float fresnel = pow(1.0 - facing, 2.6);
      vec3 light = normalize(vec3(-0.5, 0.7, 0.6));
      float spec = pow(max(dot(reflect(-light, n), vView), 0.0), 60.0);
      float soft = pow(max(dot(reflect(-normalize(vec3(0.6, -0.3, 0.5)), n), vView), 0.0), 12.0) * 0.15;
      // Etched petal lines on the glass: they turn with the sphere, so its rotation is visible.
      float angle = atan(vLocal.z, vLocal.x);
      float etch = smoothstep(0.92, 1.0, abs(sin(angle * 4.0 + vLocal.y * 2.2))) * 0.12 * (1.0 - fresnel);
      vec3 color = rim * (fresnel * 1.1 + etch) + vec3(1.0) * (spec + soft);
      float alpha = clamp(fresnel * 0.85 + spec + soft + etch, 0.0, 1.0) * opacity;
      gl_FragColor = vec4(color, alpha);
    }`,
};

/** A flame drawn on a card that always faces you: a flickering teardrop of light, hot at its heart. */
const flameShader = {
  uniforms: {
    time: { value: 0 }, heart: { value: new THREE.Color() }, outer: { value: new THREE.Color() },
    lean: { value: 0 }, height: { value: 1 }, strength: { value: 1 },
  },
  vertexShader: /* glsl */ `varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: /* glsl */ `
    uniform float time; uniform vec3 heart; uniform vec3 outer; uniform float lean; uniform float height; uniform float strength;
    varying vec2 vUv;
    ${NOISE}
    void main() {
      vec2 p = vUv * 2.0 - 1.0;        // -1..1
      p.y = (p.y + 0.55) / height;     // the flame stands on the lower part of the card
      float rise = clamp(p.y, 0.0, 1.6);
      float flicker = fbm(vec2(p.x * 2.5, p.y * 3.0 - time * 3.2)) - 0.5;
      p.x += lean * rise * rise + flicker * 0.35 * rise;
      float width = 0.62 * (1.0 - smoothstep(0.0, 1.35, rise)) * (0.75 + 0.25 * smoothstep(-0.3, 0.25, p.y));
      float body = smoothstep(width, width * 0.15, abs(p.x)) * smoothstep(-0.35, 0.05, p.y);
      float core = smoothstep(width * 0.55, 0.0, abs(p.x)) * smoothstep(-0.25, 0.1, p.y) * (1.0 - smoothstep(0.2, 0.9, rise));
      vec3 color = mix(outer, heart, core) + vec3(1.0) * core * 0.35;
      float alpha = clamp(body * 0.9 + core, 0.0, 1.0) * strength;
      gl_FragColor = vec4(color * (0.8 + strength * 0.5), alpha);
    }`,
};

const EMBERS = 36;

/** The Flame Within: a living flame floating in a clear glass sphere; it leans toward you and lives in her state. */
export const FlameOrb: React.FC<{ state: OrbState; mood: string; detail?: 'full' | 'small' }> = ({ state, mood, detail = 'full' }) => {
  const drive = useDrive(state, mood);
  const glass = useRef<THREE.Mesh>(null);
  const flame = useRef<THREE.Mesh>(null);
  const flameInner = useRef<THREE.Mesh>(null);
  const halo = useRef<THREE.Sprite>(null);
  const embers = useRef<THREE.Points>(null);
  const glassMaterial = useMemo(() => new THREE.ShaderMaterial({
    ...glassShader, uniforms: THREE.UniformsUtils.clone(glassShader.uniforms), transparent: true, depthWrite: false,
    blending: THREE.AdditiveBlending,
  }), []);
  const makeFlame = () => new THREE.ShaderMaterial({
    ...flameShader, uniforms: THREE.UniformsUtils.clone(flameShader.uniforms), transparent: true, depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const flameMaterial = useMemo(makeFlame, []);
  const innerMaterial = useMemo(makeFlame, []);
  const emberSeeds = useMemo(() => Array.from({ length: EMBERS }, () => ({
    angle: Math.random() * Math.PI * 2, radius: 0.08 + Math.random() * 0.35, phase: Math.random(), speed: 0.12 + Math.random() * 0.18,
  })), []);
  const emberPositions = useMemo(() => new Float32Array(EMBERS * 3), []);
  const emberGeometry = useMemo(() => {
    const built = new THREE.BufferGeometry();
    built.setAttribute('position', new THREE.BufferAttribute(emberPositions, 3));
    built.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1);
    return built;
  }, [emberPositions]);
  const tint = useMemo(() => new THREE.Color(), []);

  useFrame(({ camera }) => {
    const d = drive.current;
    if (glass.current) {
      glass.current.rotation.y = d.t * 0.5;
      glass.current.rotation.x = 0.25 + d.look.y * 0.1;
      glassMaterial.uniforms.time.value = d.t;
      living(d.accent, d.life, glassMaterial.uniforms.rim.value).lerp(new THREE.Color('#ffffff'), 0.25);
      glassMaterial.uniforms.opacity.value = 0.65 + d.glow * 0.35 + d.shimmer * 0.4;
    }
    const height = 0.9 + d.glow * 0.25 + d.voice * 0.35 + d.open * 0.12;
    const lean = d.look.x * 0.35 + Math.sin(d.clock * 0.7) * 0.05 + (state === 'thinking' ? Math.sin(d.clock * 2.4) * 0.18 : 0);
    [flame.current, flameInner.current].forEach((mesh, layer) => {
      if (!mesh) return;
      mesh.quaternion.copy(camera.quaternion); // always faces you
      const material = layer === 0 ? flameMaterial : innerMaterial;
      material.uniforms.time.value = d.clock * (0.8 + d.speed * 0.6) + layer * 3.1;
      material.uniforms.lean.value = lean * (layer === 0 ? 1 : 0.7);
      material.uniforms.height.value = height * (layer === 0 ? 1 : 0.72);
      material.uniforms.strength.value = (0.55 + d.glow * 0.4 + d.voice * 0.4) * (layer === 0 ? 0.8 : 1);
      living(d.heart, d.life, material.uniforms.heart.value);
      // Warm gold leads; the mood colour only tints the flame's edges.
      living(d.heart, d.life, material.uniforms.outer.value).lerp(living(d.main, d.life, tint), layer === 0 ? 0.45 : 0.1);
    });
    if (halo.current) {
      halo.current.scale.setScalar(1.1 + d.glow * 0.5 + d.voice * 0.6 + d.breath * 0.04);
      const material = halo.current.material as THREE.SpriteMaterial;
      living(d.main, d.life, material.color);
      material.opacity = 0.45 * d.glow;
    }
    if (embers.current) {
      emberSeeds.forEach((seed, i) => {
        const life = (seed.phase + d.clock * seed.speed * (0.6 + d.speed)) % 1;
        const angle = seed.angle + d.t * (0.6 + d.swirl * 2);
        emberPositions[i * 3] = Math.cos(angle) * seed.radius * (0.6 + life * 0.5);
        emberPositions[i * 3 + 1] = -0.35 + life * 1.05;
        emberPositions[i * 3 + 2] = Math.sin(angle) * seed.radius * (0.6 + life * 0.5);
      });
      (embers.current.geometry.attributes.position as THREE.BufferAttribute).needsUpdate = true;
      const material = embers.current.material as THREE.PointsMaterial;
      living(d.heart, d.life, tint);
      material.color.copy(tint);
      material.opacity = 0.35 + d.swirl * 0.4 + d.voice * 0.3;
    }
  });

  return (
    <group>
      <sprite ref={halo} scale={1.4}>
        <spriteMaterial map={glow()} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
      </sprite>
      <mesh ref={flame} material={flameMaterial} position={[0, -0.05, 0]}>
        <planeGeometry args={[0.9, 1.25]} />
      </mesh>
      <mesh ref={flameInner} material={innerMaterial} position={[0, -0.07, 0.01]}>
        <planeGeometry args={[0.6, 0.9]} />
      </mesh>
      {detail === 'full' && (
        <points ref={embers} geometry={emberGeometry}>
          <pointsMaterial map={glow()} size={0.06} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
        </points>
      )}
      <mesh ref={glass} material={glassMaterial}>
        <sphereGeometry args={[0.85, 64, 64]} />
      </mesh>
    </group>
  );
};
