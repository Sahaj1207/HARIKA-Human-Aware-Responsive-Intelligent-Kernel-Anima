import React from 'react';
import { Mic, MicOff } from 'lucide-react';
import { useHARIKAStore } from '@/store/useHARIKAStore';

export const VoiceButton: React.FC = () => {
  const { isVoiceActive, toggleVoice, setCoreState } = useHARIKAStore();

  const handleVoiceToggle = () => {
    toggleVoice();
    if (!isVoiceActive) {
      setCoreState('listening');
    } else {
      setCoreState('idle');
    }
  };

  return (
    <button
      type="button"
      onClick={handleVoiceToggle}
      className={`p-2 rounded-full transition-all duration-300 ${
        isVoiceActive
          ? 'text-cyan-400 bg-cyan-500/20 shadow-[0_0_12px_rgba(56,189,248,0.4)] animate-pulse'
          : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
      }`}
      title={isVoiceActive ? 'Voice Listening Active' : 'Activate Voice Directive'}
    >
      {isVoiceActive ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4" />}
    </button>
  );
};
