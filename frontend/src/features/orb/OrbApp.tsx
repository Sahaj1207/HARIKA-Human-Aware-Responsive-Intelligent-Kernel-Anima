import React, { useCallback, useEffect, useRef, useState } from 'react';
import { CoreCanvas } from '@/components/core/engine';
import { chatService } from '@/services/api/chat';
import { userStorage } from '@/features/onboarding/storage';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { useLiveEvents } from '@/hooks/useLiveEvents';
import type { CoreState } from '@/types';

const isDesktopApp = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;

async function hideOrb(): Promise<void> {
  if (!isDesktopApp) return;
  const { getCurrentWindow } = await import('@tauri-apps/api/window');
  await getCurrentWindow().hide();
}

interface Exchange {
  role: 'user' | 'assistant';
  content: string;
}

/**
 * The floating "Ask HARIKA" widget summoned with Ctrl+Shift+Space.
 * It shares the backend (and so memory, context and pending confirmations)
 * with the main window, but keeps its own short exchange history.
 */
export const OrbApp: React.FC = () => {
  const [input, setInput] = useState('');
  const [reply, setReply] = useState<string | null>(null);
  const [state, setState] = useState<CoreState>('idle');
  const history = useRef<Exchange[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const activity = useHARIKAStore((s) => s.activity);

  useLiveEvents({ announceReminders: false });

  // Every time the orb is summoned, start with the cursor in the input.
  useEffect(() => {
    const focusInput = () => {
      inputRef.current?.focus();
      inputRef.current?.select();
    };
    window.addEventListener('focus', focusInput);
    focusInput();
    return () => window.removeEventListener('focus', focusInput);
  }, []);

  const dismiss = useCallback(() => {
    setInput('');
    setReply(null);
    setState('idle');
    void hideOrb();
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') dismiss();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [dismiss]);

  const send = async (event: React.FormEvent) => {
    event.preventDefault();
    const message = input.trim();
    if (!message || state === 'thinking') return;
    setInput('');
    setReply(null);
    setState('thinking');
    try {
      const name = userStorage.getProfile()?.name || 'User';
      const data = await chatService.sendMessage(message, name, history.current.slice(-6));
      history.current.push({ role: 'user', content: message }, { role: 'assistant', content: data.response });
      setReply(data.response);
      setState('speaking');
    } catch {
      setReply("I can't reach my backend right now. Is HARIKA still starting up?");
      setState('error');
    }
  };

  const status = state === 'thinking' ? activity || 'Thinking…' : reply;

  return (
    <div className="h-screen w-screen p-2 select-none">
      <div className="h-full w-full flex items-start gap-4 rounded-3xl border border-cyan-400/20 bg-[#070a0f]/90 px-4 py-4 shadow-[0_0_40px_rgba(34,211,238,0.12)] backdrop-blur-xl">
        <div className="relative h-20 w-20 shrink-0" data-tauri-drag-region>
          <CoreCanvas state={state} intensity={0.9} />
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-2 pt-1">
          <form onSubmit={send}>
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask HARIKA anything…"
              spellCheck={false}
              className="w-full bg-transparent font-heading text-lg text-slate-100 placeholder:text-slate-500 outline-none select-text"
            />
          </form>
          <div className="h-px w-full bg-gradient-to-r from-cyan-400/40 via-cyan-400/10 to-transparent" />
          <p
            className={`max-h-24 overflow-y-auto text-sm leading-relaxed select-text ${
              state === 'error' ? 'text-amber-300' : state === 'thinking' ? 'text-cyan-300/80 animate-pulse' : 'text-slate-300'
            }`}
          >
            {status || <span className="text-slate-500">Press Esc to close · Enter to send</span>}
          </p>
        </div>
      </div>
    </div>
  );
};
