import React from 'react';
import { Mic, Loader2 } from 'lucide-react';
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
  const completeGeneration = useHARIKAStore((s) => s.completeGeneration);

  const isProcessing = coreState === 'thinking' || coreState === 'speaking';
  const isListening = coreState === 'listening' || isVoiceActive;

  const handleVoiceToggle = () => {
    if (isProcessing) return;

    if (isListening) {
      speechService.stop();
      setIsVoiceActive(false);
      completeGeneration();
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
          completeGeneration();
          return;
        }

        addMessage({
          role: 'user',
          content: voiceText,
          status: 'delivered',
        });

        const profile = userStorage.getProfile();
        const userName = profile?.name || 'User';

        const historyPayload = messages.slice(-12).map((m) => ({
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
          addMessage({
            role: 'assistant',
            content: "I heard you, but I can't reach my engine right now. Give it a few seconds and try again.",
            status: 'completed',
            metadata: { provider: 'offline', model: 'fallback' },
          });
          completeGeneration();
        }
      },
      onError: (error) => {
        setIsVoiceActive(false);
        setInterimTranscript(null);
        completeGeneration();

        if (error.type === 'permission-denied') {
          addMessage({
            role: 'system',
            content: 'HARIKA needs microphone access. Allow it in your system privacy settings, then try again.',
          });
        } else if (error.type === 'unsupported') {
          addMessage({
            role: 'system',
            content: "Voice input isn't available here yet.",
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
          completeGeneration();
        }
      },
    });
  };

  return (
    <button
      type="button"
      onClick={handleVoiceToggle}
      disabled={isProcessing}
      aria-pressed={isListening}
      aria-label={isListening ? 'Stop dictation' : 'Dictate'}
      title={isListening ? 'Stop dictation' : 'Dictate'}
      className={`w-8 h-8 grid place-items-center rounded-full shrink-0 transition-colors disabled:opacity-40 ${
        isListening ? 'bg-danger text-white' : 'text-label-2 hover:text-label hover:bg-fill'
      }`}
    >
      {isProcessing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mic className="w-[18px] h-[18px]" strokeWidth={2.2} />}
    </button>
  );
};
