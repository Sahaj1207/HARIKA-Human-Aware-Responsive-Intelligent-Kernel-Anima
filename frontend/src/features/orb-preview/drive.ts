import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

/** The states the orb shows (HARIKA's CoreState, simplified). */
export type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'error';

/** Mood palettes: heart (the warm centre), main (body) and accent (edges and highlights). */
export const PALETTES: Record<string, { heart: string; main: string; accent: string }> = {
  warm: { heart: '#ffd27a', main: '#c86bff', accent: '#5aa8ff' },
  cheerful: { heart: '#fff0a0', main: '#ff8a5c', accent: '#ff5fa2' },
  calm: { heart: '#c9fff1', main: '#3fc5c9', accent: '#4f7dff' },
  empathetic: { heart: '#ffd0e6', main: '#a26bff', accent: '#ff7ac8' },
  serious: { heart: '#dfe8ff', main: '#4d6bff', accent: '#6fd6ff' },
};

/** How each state feels: turning speed, openness, brightness, swirl and liveliness. */
const TARGETS: Record<OrbState, { speed: number; open: number; glow: number; swirl: number; life: number }> = {
  idle: { speed: 0.25, open: 0.35, glow: 0.75, swirl: 0.2, life: 1 },
  listening: { speed: 0.35, open: 1, glow: 1.15, swirl: 0.3, life: 1 },
  thinking: { speed: 1.6, open: 0.55, glow: 1.05, swirl: 1, life: 1 },
  speaking: { speed: 0.5, open: 0.7, glow: 1, swirl: 0.4, life: 1 },
  error: { speed: 0.12, open: 0.15, glow: 0.35, swirl: 0.1, life: 0 },
};

export interface Drive {
  t: number; // seconds, advanced by `speed` (so a faster state turns faster without jumps)
  clock: number; // real seconds
  speed: number;
  open: number; // 0 closed .. 1 opening toward you (listening)
  glow: number;
  swirl: number;
  life: number; // 1 colourful .. 0 drained (error)
  voice: number; // 0..1 loudness of her voice or yours
  breath: number; // -1..1 slow breathing
  shimmer: number; // 0..1, a soft flash every so often while resting
  look: THREE.Vector2; // where to lean, toward the pointer (-1..1)
  heart: THREE.Color;
  main: THREE.Color;
  accent: THREE.Color;
}

const GREY = new THREE.Color('#8a8f99');

/** Smoothly moves every orb parameter toward the current state and mood, once per frame. */
export function useDrive(state: OrbState, mood: string): React.MutableRefObject<Drive> {
  const drive = useRef<Drive>({
    t: 0, clock: 0, speed: 0.25, open: 0.35, glow: 0.75, swirl: 0.2, life: 1, voice: 0, breath: 0, shimmer: 0,
    look: new THREE.Vector2(), heart: new THREE.Color(PALETTES.warm.heart), main: new THREE.Color(PALETTES.warm.main),
    accent: new THREE.Color(PALETTES.warm.accent),
  });
  const nextShimmer = useRef(6);
  const colors = useMemo(() => {
    const palette = PALETTES[mood] ?? PALETTES.warm;
    return { heart: new THREE.Color(palette.heart), main: new THREE.Color(palette.main), accent: new THREE.Color(palette.accent) };
  }, [mood]);

  useFrame((frame, delta) => {
    const d = drive.current;
    const dt = Math.min(delta, 0.05);
    const k = 1 - Math.exp(-dt * 3); // ease toward targets over about a second
    const target = TARGETS[state];
    d.clock += dt;
    d.speed += (target.speed - d.speed) * k;
    d.open += (target.open - d.open) * k;
    d.glow += (target.glow - d.glow) * k;
    d.swirl += (target.swirl - d.swirl) * k;
    d.life += (target.life - d.life) * k;
    d.t += dt * d.speed;
    d.breath = Math.sin(d.clock * 1.1);

    // A preview stand-in for real loudness: speech-like bursts while speaking, softer while listening.
    const talking = state === 'speaking' ? 1 : state === 'listening' ? 0.55 : 0;
    const syllables = Math.abs(Math.sin(d.clock * 8.3)) * (0.55 + 0.45 * Math.sin(d.clock * 2.1)) * (0.7 + 0.3 * Math.sin(d.clock * 13.7));
    d.voice += (talking * syllables - d.voice) * (1 - Math.exp(-dt * 14));

    if (state === 'idle' && d.clock > nextShimmer.current) {
      d.shimmer = 1;
      nextShimmer.current = d.clock + 7 + Math.random() * 8;
    }
    d.shimmer = Math.max(0, d.shimmer - dt * 0.9);

    // Attention: lean a little toward the pointer.
    d.look.lerp(new THREE.Vector2(frame.pointer.x, frame.pointer.y), 1 - Math.exp(-dt * 2));

    d.heart.lerp(colors.heart, k * 0.6);
    d.main.lerp(colors.main, k * 0.6);
    d.accent.lerp(colors.accent, k * 0.6);
  });
  return drive;
}

/** A colour drained toward grey when HARIKA has a problem (life 0). */
export function living(color: THREE.Color, life: number, out = new THREE.Color()): THREE.Color {
  return out.copy(GREY).lerp(color, life);
}

let glowTexture: THREE.Texture | null = null;

/** A soft round light, for halos and glows (made once). */
export function glow(): THREE.Texture {
  if (glowTexture) return glowTexture;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 128;
  const g = canvas.getContext('2d')!;
  const gradient = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gradient.addColorStop(0, 'rgba(255,255,255,1)');
  gradient.addColorStop(0.25, 'rgba(255,255,255,0.45)');
  gradient.addColorStop(0.6, 'rgba(255,255,255,0.08)');
  gradient.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gradient;
  g.fillRect(0, 0, 128, 128);
  glowTexture = new THREE.CanvasTexture(canvas);
  return glowTexture;
}
