import React, { useState } from 'react';
import { Send, Terminal } from 'lucide-react';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { VoiceButton } from './VoiceButton';

export const CommandBar: React.FC = () => {
  const [input, setInput] = useState('');
  const { addMessage, setCoreState } = useHARIKAStore();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    // 1. Post user command
    addMessage({
      sender: 'user',
      content: input.trim(),
    });

    const userQuery = input.trim();
    setInput('');

    // 2. Set core visual state to processing
    setCoreState('processing');

    // 3. Simulated OS response flow placeholder
    setTimeout(() => {
      setCoreState('speaking');
      addMessage({
        sender: 'harika',
        content: `Directive acknowledged: "${userQuery}". Processing command sequence.`,
      });

      setTimeout(() => {
        setCoreState('idle');
      }, 2500);
    }, 1200);
  };

  return (
    <div className="w-full max-w-2xl mx-auto px-4 pb-6 pt-2">
      <form
        onSubmit={handleSubmit}
        className="surface-translucent rounded-full px-4 py-2.5 flex items-center space-x-3 border border-white/10 shadow-2xl transition-all duration-300 focus-within:border-sky-500/40"
      >
        <Terminal className="w-4 h-4 text-slate-400 shrink-0 ml-1" />

        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Command HARIKA OS..."
          className="flex-1 bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none font-sans"
        />

        <VoiceButton />

        <button
          type="submit"
          disabled={!input.trim()}
          className="p-2 rounded-full text-slate-400 hover:text-cyan-400 disabled:opacity-30 disabled:hover:text-slate-400 transition-colors"
          title="Execute Directive"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
};
