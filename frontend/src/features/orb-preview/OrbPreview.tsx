import React, { useEffect, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { ConstellationOrb } from './ConstellationOrb';
import { FlameOrb } from './FlameOrb';
import { LotusOrb } from './LotusOrb';
import { PALETTES, type OrbState } from './drive';

type Design = 'lotus' | 'flame' | 'constellation';

const DESIGNS: { id: Design; name: string; idea: string }[] = [
  { id: 'lotus', name: 'Lotus of Light', idea: 'Glass petals around a warm heart. They breathe, open toward you, turn while she thinks.' },
  { id: 'flame', name: 'The Flame Within', idea: 'A living flame in a clear glass sphere. It leans toward you and burns with her voice.' },
  { id: 'constellation', name: 'Living Constellation', idea: 'Points of light forming a sphere: swirling, rippling, parting for you.' },
];

const STATES: { id: OrbState; label: string }[] = [
  { id: 'idle', label: 'Resting' },
  { id: 'listening', label: 'Listening' },
  { id: 'thinking', label: 'Thinking' },
  { id: 'speaking', label: 'Speaking' },
  { id: 'error', label: 'Problem' },
];

const SCENE: { state: OrbState; seconds: number }[] = [
  { state: 'idle', seconds: 4 }, { state: 'listening', seconds: 3.5 }, { state: 'thinking', seconds: 3 },
  { state: 'speaking', seconds: 5 }, { state: 'idle', seconds: 3 },
];

const Orb: React.FC<{ design: Design; state: OrbState; mood: string; size: number; small?: boolean }> = ({
  design, state, mood, size, small,
}) => {
  const detail = small ? 'small' : 'full';
  return (
    <div style={{ width: size, height: size }}>
      <Canvas
        dpr={[1, 2]}
        camera={{ position: [0, 0, 3.1], fov: 40 }}
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
        style={{ width: size, height: size }}
      >
        <ambientLight intensity={0.55} />
        <pointLight position={[2, 3, 4]} intensity={30} />
        <pointLight position={[-3, -1, 2]} intensity={12} color="#9fb6ff" />
        {design === 'lotus' && <LotusOrb state={state} mood={mood} detail={detail} />}
        {design === 'flame' && <FlameOrb state={state} mood={mood} detail={detail} />}
        {design === 'constellation' && <ConstellationOrb state={state} mood={mood} detail={detail} />}
      </Canvas>
    </div>
  );
};

const Choice: React.FC<{ active: boolean; onClick: () => void; children: React.ReactNode }> = ({ active, onClick, children }) => (
  <button
    type="button"
    onClick={onClick}
    aria-pressed={active}
    className={`px-3 py-1.5 rounded-full t-callout transition-colors ${active ? 'bg-accent text-white' : 'bg-fill text-label hover:bg-fill/70'}`}
  >
    {children}
  </button>
);

/** Development only (index.html?window=orb-preview): the three orb designs, live, to choose HARIKA's look. */
export const OrbPreview: React.FC = () => {
  const [state, setState] = useState<OrbState>('idle');
  const [mood, setMood] = useState('warm');
  const [dark, setDark] = useState(true);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing) return;
    let step = 0;
    let timer: ReturnType<typeof setTimeout>;
    const next = () => {
      setState(SCENE[step].state);
      timer = setTimeout(() => {
        step += 1;
        if (step < SCENE.length) next();
        else setPlaying(false);
      }, SCENE[step].seconds * 1000);
    };
    next();
    return () => clearTimeout(timer);
  }, [playing]);

  return (
    <div className={dark ? 'dark' : ''} style={{ minHeight: '100vh', background: dark ? '#05060a' : '#f2f2f7', color: dark ? '#f5f5f7' : '#1c1c1e' }}>
      <div className="max-w-6xl mx-auto px-6 py-8 space-y-8">
        <header className="space-y-1">
          <h1 className="t-title1">HARIKA's orb: three designs</h1>
          <p className="t-callout opacity-70">All three are real 3D, moving live. Move your mouse near them: they turn toward you.</p>
        </header>

        <div className="flex flex-wrap items-center gap-2">
          {STATES.map((s) => (
            <Choice key={s.id} active={state === s.id} onClick={() => { setPlaying(false); setState(s.id); }}>{s.label}</Choice>
          ))}
          <span className="w-4" />
          <Choice active={playing} onClick={() => setPlaying(!playing)}>{playing ? 'Stop the scene' : 'Play a scene'}</Choice>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {Object.keys(PALETTES).map((m) => (
            <Choice key={m} active={mood === m} onClick={() => setMood(m)}>{m[0].toUpperCase() + m.slice(1)}</Choice>
          ))}
          <span className="w-4" />
          <Choice active={!dark} onClick={() => setDark(!dark)}>{dark ? 'Light background' : 'Dark background'}</Choice>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {DESIGNS.map((d) => (
            <figure key={d.id} className="flex flex-col items-center text-center gap-3">
              <Orb design={d.id} state={state} mood={mood} size={300} />
              <figcaption className="space-y-1 max-w-[280px]">
                <div className="t-headline">{d.name}</div>
                <div className="t-footnote opacity-70">{d.idea}</div>
              </figcaption>
            </figure>
          ))}
        </div>

        <section className="space-y-3">
          <h2 className="t-headline">At the sizes HARIKA uses</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {DESIGNS.map((d) => (
              <div key={d.id} className="flex items-end justify-center gap-6">
                <Orb design={d.id} state={state} mood={mood} size={112} />
                <Orb design={d.id} state={state} mood={mood} size={34} small />
                <Orb design={d.id} state={state} mood={mood} size={22} small />
              </div>
            ))}
          </div>
          <p className="t-footnote opacity-70">112: the chat welcome · 34: the floating orb · 22: the header.</p>
        </section>
      </div>
    </div>
  );
};
