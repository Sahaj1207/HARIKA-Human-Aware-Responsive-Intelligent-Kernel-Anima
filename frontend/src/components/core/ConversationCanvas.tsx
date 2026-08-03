import React, { useRef, useEffect } from 'react';
import { useHARIKAStore } from '@/store/useHARIKAStore';

export const ConversationCanvas: React.FC = () => {
  const messages = useHARIKAStore((s) => s.messages);
  const interimTranscript = useHARIKAStore((s) => s.interimTranscript);
  const canvasEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    canvasEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, interimTranscript]);

  return (
    <div className="w-full max-w-3xl mx-auto flex-1 overflow-y-auto px-4 py-6 space-y-6 scrollbar-thin">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex flex-col ${
            msg.sender === 'user'
              ? 'items-end'
              : msg.sender === 'system'
              ? 'items-center'
              : 'items-start'
          } space-y-1 transition-all duration-300`}
        >
          <div className="text-[10px] font-mono tracking-widest text-slate-500 uppercase px-1">
            {msg.sender === 'user'
              ? 'Direct Directive'
              : msg.sender === 'system'
              ? 'System Event'
              : 'HARIKA'}
          </div>

          <div
            className={`max-w-xl px-5 py-3.5 rounded-2xl text-sm leading-relaxed ${
              msg.sender === 'user'
                ? 'surface-translucent text-slate-100 border-slate-700/50'
                : msg.sender === 'system'
                ? 'surface-translucent-subtle text-amber-200/90 border-amber-500/20 text-center text-xs font-mono'
                : 'surface-translucent-subtle text-slate-200 border-white/5'
            }`}
          >
            {msg.content}
          </div>

          <div className="text-[9px] font-mono text-slate-600 px-1">{msg.timestamp}</div>
        </div>
      ))}

      {/* Live Interim Voice Transcript Bubble */}
      {interimTranscript && (
        <div className="flex flex-col items-start space-y-1 animate-pulse">
          <div className="text-[10px] font-mono tracking-widest text-cyan-400 uppercase px-1 flex items-center space-x-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping inline-block" />
            <span>Listening Mode Active</span>
          </div>
          <div className="max-w-xl px-5 py-3.5 rounded-2xl text-sm leading-relaxed surface-translucent text-cyan-200 border-cyan-500/30 shadow-[0_0_16px_rgba(56,189,248,0.15)]">
            {interimTranscript}
          </div>
        </div>
      )}

      <div ref={canvasEndRef} />
    </div>
  );
};
