import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Mic } from 'lucide-react';
import { env } from '@/config/env';
import { chatService } from '@/services/api/chat';
import { speakReplyIfWanted, speechService } from '@/services/api/speech';
import { userStorage } from '@/features/onboarding/storage';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { useLiveEvents } from '@/hooks/useLiveEvents';
import { HarikaOrb } from '@/components/apple/HarikaOrb';
import type { CoreState } from '@/types';

const isDesktopApp = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
const AUTO_HIDE_MS = 7000;

async function hideOrb(): Promise<void> {
  if (!isDesktopApp) return;
  const { getCurrentWindow } = await import('@tauri-apps/api/window');
  await getCurrentWindow().hide();
}

/** Positions and shows the orb (used when "Hey HARIKA" is heard). */
async function summonOrb(): Promise<void> {
  if (!isDesktopApp) return;
  const { invoke } = await import('@tauri-apps/api/core');
  await invoke('summon_orb');
}

interface Exchange {
  role: 'user' | 'assistant';
  content: string;
}

/**
 * The floating "Ask HARIKA" panel: summoned with Ctrl+Shift+Space, or by
 * saying "Hey HARIKA". It shares the backend (memory, context, pending
 * confirmations) with the main window and keeps a short exchange history.
 */
export const OrbApp: React.FC = () => {
  const [input, setInput] = useState('');
  const [reply, setReply] = useState<string | null>(null);
  const [state, setState] = useState<CoreState>('idle');
  const history = useRef<Exchange[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const voiceSession = useRef(false);
  const activity = useHARIKAStore((s) => s.activity);

  useLiveEvents({ announceReminders: false });

  const cancelAutoHide = () => clearTimeout(hideTimer.current);

  const dismiss = useCallback(() => {
    cancelAutoHide();
    voiceSession.current = false;
    setInput('');
    setReply(null);
    setState('idle');
    void speechService.stop().catch(() => undefined);
    void hideOrb();
  }, []);

  // Every time the panel is summoned, the cursor is ready in the field.
  useEffect(() => {
    const focusInput = () => {
      inputRef.current?.focus();
      inputRef.current?.select();
    };
    window.addEventListener('focus', focusInput);
    focusInput();
    return () => window.removeEventListener('focus', focusInput);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') dismiss();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [dismiss]);

  // "Hey HARIKA": the backend's voice engine drives the panel.
  useEffect(() => {
    const source = new EventSource(`${env.API_BASE_URL}/events`);
    source.addEventListener('voice', (raw) => {
      const event = JSON.parse((raw as MessageEvent).data);
      if (event.stage === 'wake') {
        cancelAutoHide();
        voiceSession.current = true;
        setInput('');
        setReply(null);
        setState('listening');
        void summonOrb();
      } else if (!voiceSession.current) {
        return;
      } else if (event.stage === 'heard') {
        setInput(event.text);
        setState('thinking');
      } else if (event.stage === 'answered') {
        setReply(event.reply || null);
        history.current.push({ role: 'user', content: event.text }, { role: 'assistant', content: event.reply || '' });
        setState('speaking');
      } else if (event.stage === 'no_speech') {
        setReply("I didn't catch that.");
        hideTimer.current = setTimeout(dismiss, 2500);
      } else if (event.stage === 'state' && event.state === 'idle') {
        setState('idle');
        hideTimer.current = setTimeout(dismiss, AUTO_HIDE_MS);
      }
    });
    return () => source.close();
  }, [dismiss]);

  const ask = async (message: string, spoken: boolean) => {
    cancelAutoHide();
    setReply(null);
    setState('thinking');
    try {
      const name = userStorage.getProfile()?.name || 'User';
      const data = await chatService.sendMessage(message, name, history.current.slice(-6), spoken);
      history.current.push({ role: 'user', content: message }, { role: 'assistant', content: data.response });
      setReply(data.response);
      setState('speaking');
      useHARIKAStore.getState().setMood(data.tone ?? 'warm');
      void speakReplyIfWanted(data.response, spoken, data.tone);
    } catch {
      setReply("I can't reach my engine right now. If HARIKA just started, try again in a few seconds.");
      setState('error');
    }
  };

  const send = (event: React.FormEvent) => {
    event.preventDefault();
    const message = input.trim();
    if (!message || state === 'thinking' || state === 'listening') return;
    voiceSession.current = false;
    void ask(message, false);
  };

  const talk = async () => {
    if (state === 'thinking' || state === 'listening') return;
    cancelAutoHide();
    voiceSession.current = false;
    setInput('');
    setReply(null);
    setState('listening');
    try {
      const text = (await speechService.listen()).trim();
      if (!text) {
        setState('idle');
        setReply("I didn't catch that.");
        return;
      }
      setInput(text);
      await ask(text, true);
    } catch {
      setState('error');
      setReply('Voice needs a one-time download first: open Settings, then Voice.');
    }
  };

  const busy = state === 'thinking' || state === 'listening';
  const status = state === 'listening' ? 'Listening…' : state === 'thinking' ? activity || 'Thinking…' : reply;

  return (
    // The window is transparent and clips anything past its edges, so the panel
    // casts no outer shadow and keeps a margin wide enough for the thinking glow.
    <div className="h-screen w-screen p-6 select-none" onMouseDown={cancelAutoHide}>
      <div data-active={busy} className="harika-glow-edge h-full w-full rounded-[26px]">
        <div className="orb-panel h-full w-full rounded-[26px] flex flex-col px-5 pt-4 pb-3">
          <form onSubmit={send} className="flex items-center gap-3.5" data-tauri-drag-region>
            <HarikaOrb state={state} size={34} />
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => {
                cancelAutoHide();
                setInput(e.target.value);
              }}
              placeholder="Ask HARIKA"
              aria-label="Ask HARIKA"
              spellCheck={false}
              className="flex-1 min-w-0 bg-transparent text-[24px] leading-8 tracking-[-0.02em] text-label placeholder:text-label-3 outline-none select-text"
            />
            <button
              type="button"
              onClick={() => void talk()}
              disabled={busy}
              aria-label="Speak to HARIKA"
              title="Speak to HARIKA"
              className={`w-9 h-9 grid place-items-center rounded-full shrink-0 transition-colors ${
                state === 'listening' ? 'bg-danger text-white' : 'text-label-2 hover:text-label hover:bg-fill disabled:opacity-40'
              }`}
            >
              <Mic className="w-5 h-5" strokeWidth={2.2} />
            </button>
          </form>
          <div className="mt-3 h-px bg-separator" />
          <p
            aria-live="polite"
            className={`mt-3 flex-1 overflow-y-auto t-body select-text ${
              state === 'error' ? 'text-danger' : busy ? 'text-label-2' : 'text-label'
            }`}
          >
            {status || <span className="text-label-3 t-callout">Type or tap the microphone. Esc to close</span>}
          </p>
        </div>
      </div>
    </div>
  );
};
