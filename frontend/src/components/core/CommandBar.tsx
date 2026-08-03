import React, { useState, useRef } from 'react';
import { Send, Terminal, Square } from 'lucide-react';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { VoiceButton } from './VoiceButton';
import { chatService } from '@/services/api/chat';
import { userStorage } from '@/features/onboarding/storage';
import { coreStateManager } from '@/services/coreState/coreStateManager';

export const CommandBar: React.FC = () => {
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const addMessage = useHARIKAStore((s) => s.addMessage);
  const messages = useHARIKAStore((s) => s.messages);
  const coreState = useHARIKAStore((s) => s.coreState);
  const setThinkingStage = useHARIKAStore((s) => s.setThinkingStage);
  const completeGeneration = useHARIKAStore((s) => s.completeGeneration);

  const isGenerating = coreState === 'thinking' || coreState === 'speaking';

  const handleStop = () => {
    completeGeneration();
    setTimeout(() => {
      inputRef.current?.focus();
    }, 50);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isGenerating) {
      handleStop();
      return;
    }

    const userQuery = input.trim();
    if (!userQuery) return;

    // 1. Post user directive
    addMessage({
      role: 'user',
      content: userQuery,
      status: 'delivered',
    });

    setInput('');

    // 2. Transition Core to THINKING via State Manager
    coreStateManager.transitionTo('thinking');
    setThinkingStage('thinking');

    // Timers for thinking stage indicators (>10s)
    const thinkingTimer = setTimeout(() => {
      setThinkingStage('still-thinking');
    }, 10000);

    const profile = userStorage.getProfile();
    const userName = profile?.name || 'User';

    const historyPayload = messages.map((m) => ({
      sender: m.role,
      role: m.role,
      content: m.content,
    }));

    try {
      const data = await chatService.sendMessage(userQuery, userName, historyPayload);
      clearTimeout(thinkingTimer);
      setThinkingStage('idle');

      // Transition to SPEAKING state
      coreStateManager.transitionTo('speaking');

      addMessage({
        role: 'assistant',
        content: data.response,
        status: 'streaming',
        metadata: {
          provider: data.provider,
          model: data.model,
          latency_ms: data.latency_ms,
        },
      });
    } catch {
      clearTimeout(thinkingTimer);
      addMessage({
        role: 'assistant',
        content: `I heard your directive "${userQuery}", but the backend engine is currently offline or unreachable.`,
        status: 'completed',
        metadata: { provider: 'offline', model: 'fallback' },
      });
      completeGeneration();
    } finally {
      clearTimeout(thinkingTimer);
      setTimeout(() => {
        inputRef.current?.focus();
      }, 100);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto px-4 pb-6 pt-2">
      <form
        onSubmit={handleSubmit}
        className="surface-translucent rounded-full px-4 py-2.5 flex items-center space-x-3 border border-white/10 shadow-2xl transition-all duration-300 focus-within:border-sky-500/40"
      >
        <Terminal className="w-4 h-4 text-slate-400 shrink-0 ml-1" />

        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={isGenerating}
          placeholder={isGenerating ? 'HARIKA is thinking...' : 'Command HARIKA OS...'}
          className="flex-1 bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none font-sans disabled:opacity-50"
        />

        <VoiceButton />

        {isGenerating ? (
          <button
            type="button"
            onClick={handleStop}
            className="p-2 rounded-full text-rose-400 hover:text-rose-300 bg-rose-500/10 border border-rose-500/30 animate-pulse transition-all cursor-pointer"
            title="Stop Response Generation"
          >
            <Square className="w-4 h-4 fill-current" />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim()}
            className="p-2 rounded-full text-slate-400 hover:text-cyan-400 disabled:opacity-30 disabled:hover:text-slate-400 transition-colors cursor-pointer"
            title="Execute Directive"
          >
            <Send className="w-4 h-4" />
          </button>
        )}
      </form>
    </div>
  );
};
