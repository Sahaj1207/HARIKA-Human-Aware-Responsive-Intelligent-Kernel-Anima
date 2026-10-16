import React, { useEffect, useMemo, useRef } from 'react';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { userStorage } from '@/features/onboarding/storage';
import { StreamingMessage } from '@/components/core/StreamingMessage';
import { HarikaOrb } from './HarikaOrb';
import type { Message } from '@/types';

/** Things HARIKA can really do today, offered when the conversation is empty. */
const SUGGESTIONS = ['Brief me on my day', "What's the latest F1 news?", 'Play lofi on YouTube', 'Remind me to stretch in 20 minutes'];

const LEGACY_SYSTEM_GREETINGS = new Set(['welcome-1']);

export interface AskOptions {
  /** The request was spoken, so the reply may be spoken back. */
  spoken?: boolean;
}

export function askHarika(text: string, options: AskOptions = {}): void {
  window.dispatchEvent(new CustomEvent('harika:ask', { detail: { text, ...options } }));
}

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 5) return 'Good evening';
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

/** "01:25 pm" -> minutes since midnight, for spacing timestamps like Messages does. */
function minutesOf(stamp: string): number | null {
  const match = /(\d{1,2}):(\d{2})\s*([ap]\.?m\.?)?/i.exec(stamp || '');
  if (!match) return null;
  let hour = Number(match[1]) % 12;
  if (!match[3] && Number(match[1]) >= 12) hour = Number(match[1]);
  if (match[3] && /p/i.test(match[3])) hour += 12;
  return hour * 60 + Number(match[2]);
}

const roleOf = (m: Message): Message['role'] => m.role ?? ((m as { sender?: string }).sender === 'user' ? 'user' : 'assistant');

const EmptyState: React.FC = () => {
  const name = userStorage.getProfile()?.name;
  return (
    <div className="h-full flex flex-col items-center justify-center text-center gap-5 px-6 pb-10">
      <HarikaOrb size={112} />
      <div className="space-y-1.5">
        <h1 className="t-large-title">
          {greeting()}
          {name ? `, ${name}` : ''}.
        </h1>
        <p className="t-body text-label-2">What can I do for you?</p>
      </div>
      <div className="flex flex-wrap justify-center gap-2 max-w-lg">
        {SUGGESTIONS.map((text) => (
          <button
            key={text}
            type="button"
            onClick={() => askHarika(text)}
            className="glass rounded-full px-4 py-2 t-callout text-label hover:brightness-105 active:scale-[0.98] transition"
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
};

const TypingBubble: React.FC<{ activity: string | null }> = ({ activity }) => (
  <div className="flex flex-col items-start gap-1 bubble-enter" aria-live="polite">
    <div className="bg-bubble-in rounded-[20px] rounded-bl-[6px] px-4 py-3 flex gap-1" aria-label="HARIKA is typing">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-2 h-2 rounded-full bg-label-2"
          style={{ animation: `typing-dot 1.2s ${i * 0.15}s infinite ease-in-out` }}
        />
      ))}
    </div>
    {activity && <span className="t-caption text-label-2 px-2">{activity}</span>}
  </div>
);

export const MessageList: React.FC = () => {
  const allMessages = useHARIKAStore((s) => s.messages);
  const interimTranscript = useHARIKAStore((s) => s.interimTranscript);
  const coreState = useHARIKAStore((s) => s.coreState);
  const activity = useHARIKAStore((s) => s.activity);
  const endRef = useRef<HTMLDivElement>(null);

  const messages = useMemo(() => allMessages.filter((m) => !LEGACY_SYSTEM_GREETINGS.has(m.id)), [allMessages]);
  const isThinking = coreState === 'thinking';

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, interimTranscript, isThinking, activity]);

  if (messages.length === 0 && !interimTranscript && !isThinking) return <EmptyState />;

  return (
    <div className="max-w-3xl mx-auto px-5 py-6" role="log" aria-label="Conversation">
      {messages.map((msg, index) => {
        const role = roleOf(msg);
        const prev = messages[index - 1];
        const next = messages[index + 1];
        const startsGroup = !prev || roleOf(prev) !== role;
        const endsGroup = !next || roleOf(next) !== role;
        const minutes = minutesOf(msg.timestamp);
        const prevMinutes = prev ? minutesOf(prev.timestamp) : null;
        const showTime = !prev || (minutes !== null && prevMinutes !== null && Math.abs(minutes - prevMinutes) >= 15);
        const isLatest = index === messages.length - 1;
        const meta = msg.metadata?.model && msg.metadata.provider !== 'system'
          ? `${msg.metadata.provider ?? ''} ${msg.metadata.model}${msg.metadata.latency_ms ? `, ${msg.metadata.latency_ms} ms` : ''}`
          : undefined;

        return (
          <React.Fragment key={msg.id}>
            {showTime && <p className="t-caption text-label-2 text-center pt-4 pb-2">{msg.timestamp}</p>}
            {role === 'system' ? (
              <p className="t-footnote text-label-2 text-center px-8 py-2">{msg.content}</p>
            ) : (
              <div className={`flex ${role === 'user' ? 'justify-end' : 'justify-start'} ${startsGroup ? 'mt-3' : 'mt-0.5'}`}>
                <div
                  title={meta}
                  className={`bubble-enter max-w-[75%] px-3.5 py-2 t-body whitespace-pre-wrap break-words select-text rounded-[20px] ${
                    role === 'user'
                      ? `bg-accent text-white ${endsGroup ? 'rounded-br-[6px]' : ''}`
                      : `bg-bubble-in text-label ${endsGroup ? 'rounded-bl-[6px]' : ''}`
                  }`}
                >
                  {isLatest && role === 'assistant' && msg.status === 'streaming' ? (
                    <StreamingMessage messageId={msg.id} content={msg.content} />
                  ) : (
                    msg.content
                  )}
                </div>
              </div>
            )}
          </React.Fragment>
        );
      })}

      {interimTranscript && (
        <div className="flex justify-end mt-3">
          <div className="max-w-[75%] px-3.5 py-2 t-body rounded-[20px] rounded-br-[6px] bg-accent/40 text-white italic">
            {interimTranscript}
          </div>
        </div>
      )}

      {isThinking && (
        <div className="mt-3">
          <TypingBubble activity={activity} />
        </div>
      )}
      <div ref={endRef} className="h-2" />
    </div>
  );
};
