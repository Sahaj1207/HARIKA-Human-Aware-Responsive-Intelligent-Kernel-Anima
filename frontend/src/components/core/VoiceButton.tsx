import React from 'react';
import { Mic, MicOff, Loader2 } from 'lucide-react';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { speechService } from '@/services/voice/speechRecognition';
import { chatService } from '@/services/api/chat';
import { userStorage } from '@/features/onboarding/storage';
import { coreStateManager } from '@/services/coreState/coreStateManager';

export const VoiceButton: React.FC = () => {
  const coreState = useHARIKAStore((s) => s.coreState);
  const isVoiceActive = useHARIKAStore((s) => s.isVoiceActive);
  const setIsVoiceActive = useHARIKAStore((s) => s.setIsVoiceActive);
  const setInterimTranscript = useHARIKAStore((s) => s.setInterimTranscript);
  const addMessage = useHARIKAStore((s) => s.addMessage);
  const messages = useHARIKAStore((s) => s.messages);

  const isProcessing = coreState === 'thinking' || coreState === 'speaking';
  const isListening = coreState === 'listening' || isVoiceActive;

  const handleVoiceToggle = () => {
    if (isProcessing) return;

    if (isListening) {
      speechService.stop();
      setIsVoiceActive(false);
      coreStateManager.transitionTo('idle');
      setInterimTranscript(null);
      return;
    }

    if (!speechService.isSupported()) {
      addMessage({
        role: 'system',
        content: 'Speech recognition is not supported in this browser. Please use Chrome or Edge.',
      });
      return;
    }

    speechService.start({
      onStart: () => {
        setIsVoiceActive(true);
        coreStateManager.transitionTo('listening');
        setInterimTranscript('Listening...');
      },
      onInterimResult: (transcript) => {
        setInterimTranscript(transcript || 'Listening...');
      },
      onFinalResult: async (transcript) => {
        setIsVoiceActive(false);
        setInterimTranscript(null);
        coreStateManager.transitionTo('thinking');

        const voiceText = transcript.trim();
        if (!voiceText) {
          coreStateManager.transitionTo('idle');
          return;
        }

        addMessage({
          role: 'user',
          content: voiceText,
          status: 'delivered',
        });

        const profile = userStorage.getProfile();
        const userName = profile?.name || 'User';

        const historyPayload = messages.map((m) => ({
          sender: m.role,
          role: m.role,
          content: m.content,
        }));

        try {
          const data = await chatService.sendMessage(voiceText, userName, historyPayload);
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
          coreStateManager.transitionTo('speaking');
          addMessage({
            role: 'assistant',
            content: `Received voice input "${voiceText}", but the backend engine is currently offline or unreachable.`,
            status: 'streaming',
            metadata: { provider: 'offline', model: 'fallback' },
          });
        }
      },
      onError: (error) => {
        setIsVoiceActive(false);
        setInterimTranscript(null);
        coreStateManager.transitionTo('idle');

        if (error.type === 'permission-denied') {
          addMessage({
            role: 'system',
            content: 'Microphone permission was denied. Please allow microphone access in browser settings.',
          });
        } else if (error.type === 'unsupported') {
          addMessage({
            role: 'system',
            content: 'Web Speech API is unsupported in this browser.',
          });
        } else if (error.type !== 'no-speech' && error.type !== 'aborted') {
          addMessage({
            role: 'system',
            content: `Voice error: ${error.message}`,
          });
        }
      },
      onEnd: () => {
        setIsVoiceActive(false);
        setInterimTranscript(null);
        if (useHARIKAStore.getState().coreState === 'listening') {
          coreStateManager.transitionTo('idle');
        }
      },
    });
  };

  return (
    <button
      type="button"
      onClick={handleVoiceToggle}
      disabled={isProcessing}
      className={`p-2.5 rounded-full transition-all duration-300 cursor-pointer disabled:cursor-not-allowed disabled:opacity-40 ${
        isListening
          ? 'text-cyan-300 bg-cyan-500/20 border border-cyan-400/40 shadow-[0_0_16px_rgba(56,189,248,0.5)] animate-pulse'
          : 'text-slate-400 hover:text-slate-100 hover:bg-white/5 border border-transparent'
      }`}
      title={
        isProcessing
          ? 'HARIKA is processing...'
          : isListening
          ? 'Stop Voice Input'
          : 'Activate Push-to-Talk Voice Input'
      }
    >
      {isProcessing ? (
        <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
      ) : isListening ? (
        <Mic className="w-4 h-4" />
      ) : (
        <MicOff className="w-4 h-4" />
      )}
    </button>
  );
};
