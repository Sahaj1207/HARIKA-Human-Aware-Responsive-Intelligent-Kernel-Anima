import React, { useEffect, useRef, useState } from 'react';
import { env } from '@/config/env';
import { speechService } from '@/services/api/speech';

/**
 * The screen glow (window "glow"): the edges of the whole screen light up while
 * HARIKA listens (breathing with the user's voice), thinks (a quick swirl), speaks
 * (pulsing with her own voice) or works on the screen (a bright light sweeping
 * around, "hands off for a moment"). A heads-up sends one sweep around the edge.
 *
 * The window is transparent and click-through; it's shown only while something is
 * happening and hidden again after the glow fades, so idle costs nothing.
 */

type Mode = 'off' | 'listening' | 'thinking' | 'speaking' | 'working' | 'sweep';

const isDesktopApp = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
const FADE_MS = 700;
const SWEEP_MS = 1900;

// Colours per mood, matching the orb (the latest reply's tone).
const PALETTES: Record<string, [string, string, string, string]> = {
  warm: ['#0a84ff', '#bf5af2', '#ff375f', '#ff9f0a'],
  cheerful: ['#ff9f0a', '#ff375f', '#ffd60a', '#40c8e0'],
  excited: ['#ff375f', '#ff9f0a', '#ffd60a', '#bf5af2'],
  playful: ['#40c8e0', '#ff375f', '#bf5af2', '#ffd60a'],
  empathetic: ['#bf5af2', '#5e5ce6', '#ff375f', '#7d7aff'],
  calm: ['#40c8e0', '#0a84ff', '#5e5ce6', '#30d158'],
  apologetic: ['#5e5ce6', '#bf5af2', '#5a6c8a', '#0a84ff'],
  serious: ['#5e5ce6', '#0a84ff', '#5a6c8a', '#40c8e0'],
};

async function setVisible(visible: boolean): Promise<void> {
  if (!isDesktopApp) return;
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    await invoke(visible ? 'show_glow' : 'hide_glow');
  } catch {
    // The glow is decoration; it never affects HARIKA itself.
  }
}

export const GlowApp: React.FC = () => {
  const [mode, setMode] = useState<Mode>('off');
  const [shown, setShown] = useState(false); // fading out keeps it shown a moment longer
  const [level, setLevel] = useState(0);
  const [mood, setMood] = useState('warm');
  const settings = useRef({ glow: true, headsUp: true, checked: 0 });
  const voiceActive = useRef(false);
  const timers = useRef<{ fade?: ReturnType<typeof setTimeout>; sweep?: ReturnType<typeof setTimeout> }>({});

  // The switches in Settings > Voice, re-read every minute.
  const refreshSettings = async () => {
    if (Date.now() - settings.current.checked < 60_000) return;
    try {
      const { settings: s } = await speechService.status();
      settings.current = { glow: s.screen_glow !== false, headsUp: s.glow_heads_up !== false, checked: Date.now() };
    } catch {
      settings.current.checked = Date.now();
    }
  };

  useEffect(() => {
    void refreshSettings();
    const go = (next: Mode) => {
      void refreshSettings();
      if (next !== 'off' && next !== 'sweep' && !settings.current.glow) return;
      clearTimeout(timers.current.fade);
      if (next === 'off') {
        setMode('off');
        timers.current.fade = setTimeout(() => {
          setShown(false);
          void setVisible(false);
        }, FADE_MS);
        return;
      }
      setShown(true);
      void setVisible(true);
      setMode(next);
    };

    if (import.meta.env.DEV) {
      // Development only: try the looks in a browser, e.g. harikaGlow('listening', 0.7, 'calm').
      (window as unknown as Record<string, unknown>).harikaGlow = (next: Mode, nextLevel = 0.5, nextMood = 'warm') => {
        setMood(nextMood);
        setLevel(nextLevel);
        go(next);
      };
    }

    const source = new EventSource(`${env.API_BASE_URL}/events`);
    source.addEventListener('voice', (raw) => {
      const event = JSON.parse((raw as MessageEvent).data);
      if (event.stage === 'wake' || event.stage === 'interrupted') {
        voiceActive.current = true;
        go('listening');
      } else if (event.stage === 'answered' && event.tone) {
        setMood(PALETTES[event.tone] ? event.tone : 'warm');
      } else if (event.stage === 'no_speech') {
        voiceActive.current = false;
        go('off');
      } else if (event.stage === 'state') {
        if (event.state === 'listening' || event.state === 'thinking' || event.state === 'speaking') {
          voiceActive.current = true;
          go(event.state);
        } else if (event.state === 'idle' || event.state === 'off') {
          voiceActive.current = false;
          go('off');
        }
      }
    });
    source.addEventListener('voice_level', (raw) => {
      const { level: next } = JSON.parse((raw as MessageEvent).data) as { level: number };
      setLevel((previous) => previous * 0.4 + next * 0.6); // smooth, but quick to follow speech
    });
    source.addEventListener('voice_follow_up', (raw) => {
      const event = JSON.parse((raw as MessageEvent).data) as { phase: string; text?: string };
      if (event.phase === 'listening') go('listening');
      else if (!event.text) go('off');
    });
    // HARIKA acting on the screen: opening apps, typing replies, pressing buttons, multi-step tasks.
    source.addEventListener('step', (raw) => {
      const step = JSON.parse((raw as MessageEvent).data) as { index: number; total: number; status: string; label: string };
      if (step.label === 'thinking') return;
      if (step.status === 'started') go('working');
      else if (step.index === step.total || step.status !== 'completed') go(voiceActive.current ? 'thinking' : 'off');
    });
    source.addEventListener('activity', (raw) => {
      const { text } = JSON.parse((raw as MessageEvent).data) as { text: string };
      go(text ? 'working' : voiceActive.current ? 'thinking' : 'off');
    });
    source.addEventListener('heads_up', () => {
      if (!settings.current.headsUp || voiceActive.current) return;
      go('sweep');
      clearTimeout(timers.current.sweep);
      timers.current.sweep = setTimeout(() => go('off'), SWEEP_MS);
    });
    return () => {
      source.close();
      clearTimeout(timers.current.fade);
      clearTimeout(timers.current.sweep);
    };
  }, []);

  // Listening and speaking follow the voice; the other modes have their own rhythm.
  const live = mode === 'listening' || mode === 'speaking' ? level : mode === 'working' || mode === 'sweep' ? 0.85 : 0.35;
  const [c1, c2, c3, c4] = mode === 'working' || mode === 'sweep' ? PALETTES.warm : PALETTES[mood] ?? PALETTES.warm;
  const style = {
    '--glow-c1': c1,
    '--glow-c2': c2,
    '--glow-c3': c3,
    '--glow-c4': c4,
    '--glow-level': live.toFixed(3),
  } as React.CSSProperties;

  if (!shown) return null;
  return (
    <div className="harika-screen-glow" data-mode={mode} style={style} aria-hidden>
      {(['wash', 'halo', 'edge'] as const).map((layer) => (
        <div key={layer} className={`harika-screen-glow__layer harika-screen-glow__layer--${layer}`}>
          <div className="harika-screen-glow__ring" />
        </div>
      ))}
    </div>
  );
};
