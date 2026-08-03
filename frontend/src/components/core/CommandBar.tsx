import React, { useState } from 'react';
import { Send, Terminal } from 'lucide-react';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { VoiceButton } from './VoiceButton';
import { chatService } from '@/services/api/chat';
import { userStorage } from '@/features/onboarding/storage';

export const CommandBar: React.FC = () => {
  const [input, setInput] = useState('');
  const addMessage = useHARIKAStore((s) => s.addMessage);
  const setCoreState = useHARIKAStore((s) => s.setCoreState);
  const messages = useHARIKAStore((s) => s.messages);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const userQuery = input.trim();
    if (!userQuery) return;

    // 1. Post user directive to ConversationCanvas
    addMessage({
      sender: 'user',
      content: userQuery,
    });

    setInput('');

    // 2. Transition core visual state to processing
    setCoreState('processing');

    // 3. Fetch user profile name
    const profile = userStorage.getProfile();
    const userName = profile?.name || 'User';

    // 4. Format conversation history for Cognition Engine
    const historyPayload = messages.map((m) => ({
      sender: m.sender,
      role: m.sender === 'user' ? 'user' : 'assistant',
      content: m.content,
    }));

    try {
      // Send chat directive to backend /api/v1/chat
      const data = await chatService.sendMessage(userQuery, userName, historyPayload);

      setCoreState('speaking');
      addMessage({
        sender: 'harika',
        content: data.response,
      });

      setTimeout(() => {
        setCoreState('idle');
      }, 1800);
    } catch {
      setCoreState('speaking');
      addMessage({
        sender: 'harika',
        content: `I heard your directive "${userQuery}", but the backend engine is currently offline or unreachable.`,
      });

      setTimeout(() => {
        setCoreState('idle');
      }, 2000);
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
