import React, { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { glow, living, useDrive, type OrbState, type Ring } from './drive';

/** Wider, pointed lotus petals in three rings: in points of light a lotus needs bolder petal shapes. */
const STAR_RINGS: Ring[] = [
  { count: 6, length: 0.42, width: 0.26, lift: 0.55, spin: 1, offset: 0 },
  { count: 8, length: 0.62, width: 0.3, lift: 1.0, spin: -1, offset: Math.PI / 8 },
  { count: 10, length: 0.78, width: 0.3, lift: 1.38, spin: 0.6, offset: 0 }, // the outer petals lie open
];

/** Every star knows its petal (ring shape, angle) and where on the petal it sits; the shader builds the
 * petal there each frame, so blooming, breathing and turning move the stars like a real flower. */
const starShader = {
  uniforms: {
    time: { value: 0 }, open: { value: 0 }, breath: { value: 0 }, voice: { value: 0 }, swirl: { value: 0 },
    turn: { value: 0 }, size: { value: 1 }, heartColor: { value: new THREE.Color() },
    bodyColor: { value: new THREE.Color() }, accentColor: { value: new THREE.Color() }, brightness: { value: 1 },
  },
  vertexShader: /* glsl */ `
    uniform float time; uniform float open; uniform float breath; uniform float voice; uniform float swirl; uniform float turn;
    uniform float size; uniform vec3 heartColor; uniform vec3 bodyColor; uniform vec3 accentColor;
    attribute vec2 petalUv;    // u across the petal, v from heart to tip
    attribute vec4 petal;      // length, width, lift, angle
    attribute vec2 ringInfo;   // spin direction, ring index
    attribute float seed;
    varying vec3 vColor; varying float vAlpha;
    void main() {
      float u = petalUv.x, v = petalUv.y;
      float len = petal.x, width = petal.y, lift = petal.z, angle = petal.w;
      float halfWidth = pow(sin(3.14159 * min(v * 1.04, 1.0)), 0.9) * (1.0 - 0.45 * v) * width;
      float across = (u - 0.5) * 2.0;
      vec3 p = vec3(across * halfWidth, v * len, -0.6 * across * across * halfWidth + 0.4 * pow(v, 2.4) * len);
      // Tilt the petal outward: more when open (listening), breathing, rippling with the voice.
      float tilt = lift * (0.72 + open * 0.45) + breath * 0.035 + sin(time * 7.0 + angle * 3.0) * voice * 0.14;
      float c = cos(tilt), s = sin(tilt);
      p = vec3(p.x, c * p.y - s * p.z, s * p.y + c * p.z);
      p.z += 0.03;
      float a = angle + ringInfo.x * turn * swirl * 1.4;
      float ca = cos(a), sa = sin(a);
      p = vec3(ca * p.x + sa * p.z, p.y, -sa * p.x + ca * p.z);
      vec4 mv = modelViewMatrix * vec4(p, 1.0);
      float twinkle = 0.6 + 0.4 * sin(time * 2.6 + seed * 50.0);
      float edge = max(smoothstep(0.6, 0.95, abs(across)), 0.7 * (1.0 - smoothstep(0.0, 0.12, abs(across))));
      gl_PointSize = size * twinkle * (1.0 + edge * 0.5) * (300.0 / -mv.z);
      gl_Position = projectionMatrix * mv;
      vec3 bodyTint = mix(bodyColor, accentColor, ringInfo.y / 3.0);
      vColor = mix(heartColor, bodyTint, smoothstep(0.0, 0.85, v));
      vAlpha = (0.15 + 0.85 * edge) * (0.65 + 0.35 * (1.0 - v * 0.5));
    }`,
  fragmentShader: /* glsl */ `
    uniform float brightness; varying vec3 vColor; varying float vAlpha;
    void main() {
      float d = length(gl_PointCoord - 0.5);
      float a = smoothstep(0.5, 0.0, d);
      gl_FragColor = vec4(vColor * brightness * (1.0 + a), a * vAlpha);
    }`,
};

function starPetals(perPetal: number, rings: Ring[]): THREE.BufferGeometry {
  const total = rings.reduce((n, r) => n + r.count * perPetal, 0);
  const petalUv = new Float32Array(total * 2);
  const petal = new Float32Array(total * 4);
  const ringInfo = new Float32Array(total * 2);
  const seed = new Float32Array(total);
  let i = 0;
  rings.forEach((ring, r) => {
    for (let k = 0; k < ring.count; k++) {
      const angle = ring.offset + (k / ring.count) * Math.PI * 2;
      for (let n = 0; n < perPetal; n++) {
        // Stars trace each petal's two edges evenly from base to tip and its centre vein (so it reads
        // as a lotus petal); a few are scattered faintly over its surface.
        const role = n % 5; // 0, 1, 3, 4: the two edges (they carry the shape); 2: the centre vein
        const step = (Math.floor(n / 5) + Math.random() * 0.3) / Math.ceil(perPetal / 5);
        let u: number, v: number;
        if (role === 2) { u = 0.5; v = 0.1 + step * 0.7; }
        else { u = role % 2 === 0 ? 0.0 : 1.0; v = Math.min(1, step + (role > 2 ? 0.5 / Math.ceil(perPetal / 5) : 0)); }
        petalUv.set([u, v], i * 2);
        petal.set([ring.length, ring.width, ring.lift, angle], i * 4);
        ringInfo.set([ring.spin, r], i * 2);
        seed[i] = Math.random();
        i++;
      }
    }
  });
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(total * 3), 3)); // built in the shader
  geometry.setAttribute('petalUv', new THREE.BufferAttribute(petalUv, 2));
  geometry.setAttribute('petal', new THREE.BufferAttribute(petal, 4));
  geometry.setAttribute('ringInfo', new THREE.BufferAttribute(ringInfo, 2));
  geometry.setAttribute('seed', new THREE.BufferAttribute(seed, 1));
  geometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 2);
  return geometry;
}

/** The Starlit Lotus: a lotus drawn in points of light, the constellation and the flower in one. */
export const StarLotusOrb: React.FC<{ state: OrbState; mood: string; signature?: string; detail?: 'full' | 'small' }> = ({
  state, mood, signature = '', detail = 'full',
}) => {
  const drive = useDrive(state, mood, signature);
  const root = useRef<THREE.Group>(null);
  const heart = useRef<THREE.Sprite>(null);
  const aura = useRef<THREE.Sprite>(null);
  const geometry = useMemo(() => starPetals(detail === 'small' ? 30 : 110, STAR_RINGS), [detail]);
  const stamens = useMemo(() => {
    const count = 30;
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2;
      const r = 0.09 + (i % 2) * 0.05;
      positions.set([Math.cos(angle) * r, 0.14 + (i % 3) * 0.025, Math.sin(angle) * r], i * 3);
    }
    const built = new THREE.BufferGeometry();
    built.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    return built;
  }, []);
  const stamenRef = useRef<THREE.Points>(null);
  const material = useMemo(() => new THREE.ShaderMaterial({
    ...starShader, uniforms: THREE.UniformsUtils.clone(starShader.uniforms), transparent: true, depthWrite: false,
    blending: THREE.AdditiveBlending,
  }), []);

  useFrame(({ gl, size }) => {
    const d = drive.current;
    if (root.current) {
      // From above at an angle: you look down into the flower and see its rosette, with depth.
      root.current.rotation.x = -0.95 - d.look.y * 0.18;
      root.current.rotation.z = -d.look.x * 0.12;
      root.current.rotation.y = d.t * 0.5;
      root.current.position.y = 0.05 + d.breath * 0.02;
      root.current.scale.setScalar(1.25);
    }
    if (stamenRef.current) {
      stamenRef.current.rotation.y = -d.t * 0.8;
      const stamenMaterial = stamenRef.current.material as THREE.PointsMaterial;
      living(d.heart, d.life, stamenMaterial.color);
      stamenMaterial.opacity = 0.65 + d.voice * 0.35 + d.shimmer * 0.4;
      stamenMaterial.size = (detail === 'small' ? 0.1 : 0.06) * (1 + d.voice * 0.4);
    }
    const u = material.uniforms;
    u.time.value = d.clock;
    u.turn.value = d.t;
    u.open.value = d.open;
    u.breath.value = d.breath;
    u.voice.value = d.voice;
    u.swirl.value = d.swirl;
    u.size.value = (detail === 'small' ? 0.1 : 0.045) * gl.getPixelRatio() * Math.min(1, size.height / 300);
    u.brightness.value = 0.65 + d.glow * 0.55 + d.shimmer * 0.6 + d.voice * 0.3;
    living(d.heart, d.life, u.heartColor.value);
    living(d.main, d.life, u.bodyColor.value);
    living(d.accent, d.life, u.accentColor.value);
    if (heart.current) {
      heart.current.scale.setScalar(0.18 + d.glow * 0.06 + d.voice * 0.2 + d.breath * 0.01);
      living(d.heart, d.life, (heart.current.material as THREE.SpriteMaterial).color);
    }
    if (aura.current) {
      aura.current.scale.setScalar(2.6 + d.voice * 0.3);
      const sprite = aura.current.material as THREE.SpriteMaterial;
      living(d.main, d.life, sprite.color);
      sprite.opacity = 0.16 * d.glow + d.shimmer * 0.1;
    }
  });

  return (
    <group>
      <sprite ref={aura} renderOrder={-1}>
        <spriteMaterial map={glow()} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
      </sprite>
      <group ref={root}>
        <points geometry={geometry} material={material} />
        <points ref={stamenRef} geometry={stamens}>
          <pointsMaterial map={glow()} size={0.06} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
        </points>
        <sprite ref={heart} position={[0, 0.1, 0]}>
          <spriteMaterial map={glow()} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
        </sprite>
      </group>
    </group>
  );
};
