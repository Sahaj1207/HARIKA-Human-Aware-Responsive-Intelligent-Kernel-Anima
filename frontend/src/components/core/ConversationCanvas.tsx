import React, { useRef, useEffect } from 'react';
import { Cpu, Clock, Layers } from 'lucide-react';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { StreamingMessage } from './StreamingMessage';

export const ConversationCanvas: React.FC = () => {
  const messages = useHARIKAStore((s) => s.messages);
  const interimTranscript = useHARIKAStore((s) => s.interimTranscript);
  const coreState = useHARIKAStore((s) => s.coreState);
  const thinkingStage = useHARIKAStore((s) => s.thinkingStage);
  const canvasEndRef = useRef<HTMLDivElement>(null);

  const isThinking = coreState === 'thinking';

  useEffect(() => {
    canvasEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, interimTranscript, isThinking, thinkingStage]);

  return (
    <div className="w-full max-w-3xl mx-auto flex-1 overflow-y-auto px-4 py-6 space-y-6 scrollbar-thin">
      {messages.map((msg, index) => {
        const isLatestAssistant =
          index === messages.length - 1 &&
          (msg.role === 'assistant' || (msg as any).sender === 'harika');
        const isStreaming = isLatestAssistant && msg.status === 'streaming';

        return (
          <div
            key={msg.id}
            className={`flex flex-col ${
              msg.role === 'user' || (msg as any).sender === 'user'
                ? 'items-end animate-in fade-in zoom-in-95 duration-200'
                : msg.role === 'system' || (msg as any).sender === 'system'
                ? 'items-center'
                : 'items-start animate-in fade-in slide-in-from-bottom-2 duration-300'
            } space-y-1`}
          >
            <div className="text-[10px] font-mono tracking-widest text-slate-500 uppercase px-1">
              {msg.role === 'user' || (msg as any).sender === 'user'
                ? 'Direct Directive'
                : msg.role === 'system' || (msg as any).sender === 'system'
                ? 'System Event'
                : 'HARIKA OS'}
            </div>

            <div
              className={`max-w-xl px-5 py-3.5 rounded-2xl text-sm leading-relaxed ${
                msg.role === 'user' || (msg as any).sender === 'user'
                  ? 'surface-translucent text-slate-100 border-slate-700/50'
                  : msg.role === 'system' || (msg as any).sender === 'system'
                  ? 'surface-translucent-subtle text-amber-200/90 border-amber-500/20 text-center text-xs font-mono'
                  : 'surface-translucent-subtle text-slate-200 border-white/5 shadow-xl'
              }`}
            >
              {isStreaming ? (
                <StreamingMessage content={msg.content} />
              ) : (
                <span>{msg.content}</span>
              )}
            </div>

            {/* Provider & Model Metadata Badges */}
            {msg.metadata && msg.metadata.provider && (
              <div className="flex items-center space-x-3 text-[9px] font-mono text-slate-500 px-1 pt-0.5">
                <span className="flex items-center space-x-1">
                  <Cpu className="w-2.5 h-2.5 text-cyan-400" />
                  <span>{msg.metadata.provider}</span>
                </span>
                {msg.metadata.model && (
                  <span className="flex items-center space-x-1">
                    <Layers className="w-2.5 h-2.5 text-indigo-400" />
                    <span>{msg.metadata.model}</span>
                  </span>
                )}
                {msg.metadata.latency_ms && (
                  <span className="flex items-center space-x-1">
                    <Clock className="w-2.5 h-2.5 text-emerald-400" />
                    <span>{msg.metadata.latency_ms}ms</span>
                  </span>
                )}
                <span>{msg.timestamp}</span>
              </div>
            )}
          </div>
        );
      })}

      {/* Dynamic Thinking Stage Indicators */}
      {isThinking && (
        <div className="flex flex-col items-start space-y-1 animate-pulse">
          <div className="text-[10px] font-mono tracking-widest text-indigo-400 uppercase px-1 flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-indigo-400 animate-ping inline-block" />
            <span>
              {thinkingStage === 'still-thinking'
                ? 'Still thinking...'
                : 'HARIKA is thinking...'}
            </span>
          </div>
          <div className="px-5 py-3 rounded-2xl text-xs font-mono surface-translucent text-indigo-200 border-indigo-500/30 flex items-center space-x-2">
            <span className="animate-bounce">.</span>
            <span className="animate-bounce delay-100">.</span>
            <span className="animate-bounce delay-200">.</span>
          </div>
        </div>
      )}

      {/* Live Voice Input Transcript */}
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
