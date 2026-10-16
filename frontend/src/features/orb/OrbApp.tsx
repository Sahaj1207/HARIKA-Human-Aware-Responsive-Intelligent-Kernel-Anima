import React, { useCallback, useEffect, useRef, useState } from 'react';
import { chatService } from '@/services/api/chat';
import { userStorage } from '@/features/onboarding/storage';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { useLiveEvents } from '@/hooks/useLiveEvents';
import { HarikaOrb } from '@/components/apple/HarikaOrb';
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
 * The floating "Ask HARIKA" panel summoned with Ctrl+Shift+Space, like Spotlight.
 * It shares the backend (memory, context, pending confirmations) with the main
 * window and keeps its own short exchange history.
 */
export const OrbApp: React.FC = () => {
  const [input, setInput] = useState('');
  const [reply, setReply] = useState<string | null>(null);
  const [state, setState] = useState<CoreState>('idle');
  const history = useRef<Exchange[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const activity = useHARIKAStore((s) => s.activity);

  useLiveEvents({ announceReminders: false });

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
      setReply("I can't reach my engine right now. If HARIKA just started, try again in a few seconds.");
      setState('error');
    }
  };

  const thinking = state === 'thinking';
  const status = thinking ? activity || 'Thinking…' : reply;

  return (
    // The window is transparent and clips anything past its edges, so the panel
    // casts no outer shadow and keeps a margin wide enough for the thinking glow.
    <div className="h-screen w-screen p-6 select-none">
      <div
        data-active={thinking}
        className="harika-glow-edge h-full w-full rounded-[26px]"
      >
        <div className="orb-panel h-full w-full rounded-[26px] flex flex-col px-5 pt-4 pb-3">
          <form onSubmit={send} className="flex items-center gap-3.5" data-tauri-drag-region>
            <HarikaOrb state={state} size={34} />
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask HARIKA"
              aria-label="Ask HARIKA"
              spellCheck={false}
              className="flex-1 min-w-0 bg-transparent text-[24px] leading-8 tracking-[-0.02em] text-label placeholder:text-label-3 outline-none select-text"
            />
          </form>
          <div className="mt-3 h-px bg-separator" />
          <p
            aria-live="polite"
            className={`mt-3 flex-1 overflow-y-auto t-body select-text ${
              state === 'error' ? 'text-danger' : thinking ? 'text-label-2' : 'text-label'
            }`}
          >
            {status || <span className="text-label-3 t-callout">Press Return to ask, Esc to close</span>}
          </p>
        </div>
      </div>
    </div>
  );
};
