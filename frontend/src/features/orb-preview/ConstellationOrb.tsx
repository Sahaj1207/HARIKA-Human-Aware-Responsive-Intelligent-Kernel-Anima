import React, { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { glow, living, useDrive, type OrbState } from './drive';

const starShader = {
  uniforms: {
    time: { value: 0 }, swirl: { value: 0 }, open: { value: 0 }, voice: { value: 0 }, breath: { value: 0 },
    size: { value: 1 }, bodyColor: { value: new THREE.Color() }, accent: { value: new THREE.Color() },
    heart: { value: new THREE.Color() }, brightness: { value: 1 }, band: { value: 0 },
  },
  vertexShader: /* glsl */ `
    uniform float time; uniform float swirl; uniform float open; uniform float voice; uniform float breath;
    uniform float size; uniform vec3 bodyColor; uniform vec3 accent; uniform vec3 heart; uniform float band;
    attribute float seed; attribute float kind; // kind 0: shell, 1: inner cluster, 2: orbiting band
    varying vec3 vColor; varying float vAlpha;
    void main() {
      vec3 p = position;
      float lat = p.y / max(length(p), 0.001);
      // Turning faster near the equator than at the poles, like a living galaxy.
      float spin = time * (0.35 + swirl * 1.4) * (1.0 - 0.55 * abs(lat));
      if (kind > 1.5) spin = -time * (0.6 + swirl * 2.2);
      float c = cos(spin), s = sin(spin);
      p = vec3(c * p.x + s * p.z, p.y, -s * p.x + c * p.z);
      // Breathing, and ripples of light running over it while she speaks.
      float r = 1.0 + breath * 0.02 + voice * 0.13 * sin(lat * 9.0 - time * 9.0 + seed * 2.0);
      if (kind < 0.5) p *= r;
      // Listening: the side facing you parts like a doorway.
      vec3 dir = normalize(p);
      float facing = smoothstep(0.55, 1.0, dir.z);
      if (kind < 0.5) p.xy *= 1.0 + open * 0.7 * facing;
      vec4 mv = modelViewMatrix * vec4(p, 1.0);
      float twinkle = 0.65 + 0.35 * sin(time * 3.0 + seed * 40.0);
      float bandShow = kind > 1.5 ? band : 1.0;
      gl_PointSize = size * twinkle * (kind > 0.5 && kind < 1.5 ? 1.5 : 1.0) * bandShow * (300.0 / -mv.z);
      gl_Position = projectionMatrix * mv;
      vColor = kind > 0.5 && kind < 1.5 ? heart : mix(bodyColor, accent, 0.5 + 0.5 * lat);
      vAlpha = (0.35 + 0.65 * (0.5 + 0.5 * dir.z)) * (1.0 - open * 0.6 * facing) * bandShow;
    }`,
  fragmentShader: /* glsl */ `
    uniform float brightness; varying vec3 vColor; varying float vAlpha;
    void main() {
      float d = length(gl_PointCoord - 0.5);
      float a = smoothstep(0.5, 0.0, d);
      gl_FragColor = vec4(vColor * brightness * (1.0 + a), a * vAlpha);
    }`,
};

function stars(count: number): { positions: Float32Array; seeds: Float32Array; kinds: Float32Array } {
  const shell = Math.round(count * 0.72);
  const inner = Math.round(count * 0.14);
  const positions = new Float32Array(count * 3);
  const seeds = new Float32Array(count);
  const kinds = new Float32Array(count);
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i++) {
    let x: number, y: number, z: number, kind: number;
    if (i < shell) {
      // Evenly spread over the sphere (a Fibonacci lattice), jittered so it looks natural.
      y = 1 - (i / (shell - 1)) * 2;
      const radius = Math.sqrt(1 - y * y);
      const theta = golden * i;
      const jitter = 0.97 + Math.random() * 0.06;
      x = Math.cos(theta) * radius * jitter; z = Math.sin(theta) * radius * jitter; y *= jitter;
      kind = 0;
    } else if (i < shell + inner) {
      const u = Math.random() * 2 - 1, phi = Math.random() * Math.PI * 2, rr = Math.cbrt(Math.random()) * 0.32;
      x = Math.sqrt(1 - u * u) * Math.cos(phi) * rr; y = u * rr; z = Math.sqrt(1 - u * u) * Math.sin(phi) * rr;
      kind = 1;
    } else {
      const angle = Math.random() * Math.PI * 2, rr = 1.25 + (Math.random() - 0.5) * 0.06;
      x = Math.cos(angle) * rr; y = (Math.random() - 0.5) * 0.04; z = Math.sin(angle) * rr;
      kind = 2;
    }
    positions.set([x, y, z], i * 3);
    seeds[i] = Math.random();
    kinds[i] = kind;
  }
  return { positions, seeds, kinds };
}

/** The Living Constellation: points of light forming a sphere that swirls, ripples, breathes and parts for you. */
export const ConstellationOrb: React.FC<{ state: OrbState; mood: string; detail?: 'full' | 'small' }> = ({ state, mood, detail = 'full' }) => {
  const drive = useDrive(state, mood);
  const group = useRef<THREE.Group>(null);
  const halo = useRef<THREE.Sprite>(null);
  const geometry = useMemo(() => {
    const data = stars(detail === 'small' ? 420 : 1300);
    const built = new THREE.BufferGeometry();
    built.setAttribute('position', new THREE.BufferAttribute(data.positions, 3));
    built.setAttribute('seed', new THREE.BufferAttribute(data.seeds, 1));
    built.setAttribute('kind', new THREE.BufferAttribute(data.kinds, 1));
    built.computeBoundingSphere();
    return built;
  }, [detail]);
  const material = useMemo(() => new THREE.ShaderMaterial({
    ...starShader, uniforms: THREE.UniformsUtils.clone(starShader.uniforms), transparent: true, depthWrite: false,
    blending: THREE.AdditiveBlending,
  }), []);

  useFrame(({ gl, size }) => {
    const d = drive.current;
    if (group.current) {
      group.current.rotation.x = 0.35 + d.look.y * 0.2;
      group.current.rotation.z = 0.12 - d.look.x * 0.15;
      group.current.scale.setScalar(0.62);
    }
    const u = material.uniforms;
    u.time.value = d.t * 2.2;
    u.swirl.value = d.swirl;
    u.open.value = Math.max(0, d.open - 0.4) / 0.6;
    u.voice.value = d.voice;
    u.breath.value = d.breath;
    // Point sizes are in device pixels: scale by the screen's sharpness so they don't shrink to nothing.
    // ...and by the canvas size, so a small orb has small stars instead of one white blob.
    u.size.value = (detail === 'small' ? 0.14 : 0.085) * gl.getPixelRatio() * Math.min(1, size.height / 300);
    u.brightness.value = 0.7 + d.glow * 0.6 + d.shimmer * 0.6;
    u.band.value = Math.min(1, Math.max(0, (d.swirl - 0.3) / 0.6));
    living(d.main, d.life, u.bodyColor.value);
    living(d.accent, d.life, u.accent.value);
    living(d.heart, d.life, u.heart.value);
    if (halo.current) {
      halo.current.scale.setScalar(0.7 + d.glow * 0.35 + d.voice * 0.45 + d.breath * 0.03);
      const sprite = halo.current.material as THREE.SpriteMaterial;
      living(d.heart, d.life, sprite.color);
      sprite.opacity = 0.55 * d.glow;
    }
  });

  return (
    <group>
      <sprite ref={halo}>
        <spriteMaterial map={glow()} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
      </sprite>
      <group ref={group}>
        <points material={material} geometry={geometry} />
      </group>
    </group>
  );
};
