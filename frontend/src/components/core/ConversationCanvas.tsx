import React, { useRef, useEffect } from 'react';
import { useHARIKAStore } from '@/store/useHARIKAStore';

export const ConversationCanvas: React.FC = () => {
  const { messages } = useHARIKAStore();
  const canvasEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    canvasEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="w-full max-w-3xl mx-auto flex-1 overflow-y-auto px-4 py-6 space-y-6 scrollbar-thin">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex flex-col ${
            msg.sender === 'user' ? 'items-end' : 'items-start'
          } space-y-1 transition-all duration-300`}
        >
          <div className="text-[10px] font-mono tracking-widest text-slate-500 uppercase px-1">
            {msg.sender === 'user' ? 'Direct Command' : 'HARIKA'}
          </div>

          <div
            className={`max-w-xl px-5 py-3.5 rounded-2xl text-sm leading-relaxed ${
              msg.sender === 'user'
                ? 'surface-translucent text-slate-100 border-slate-700/50'
                : 'surface-translucent-subtle text-slate-200 border-white/5'
            }`}
          >
            {msg.content}
          </div>

          <div className="text-[9px] font-mono text-slate-600 px-1">{msg.timestamp}</div>
        </div>
      ))}
      <div ref={canvasEndRef} />
    </div>
  );
};
