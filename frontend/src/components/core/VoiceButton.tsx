import React from 'react';
import { Mic, MicOff, Loader2 } from 'lucide-react';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { speechService } from '@/services/voice/speechRecognition';
import { chatService } from '@/services/api/chat';
import { userStorage } from '@/features/onboarding/storage';

export const VoiceButton: React.FC = () => {
  const coreState = useHARIKAStore((s) => s.coreState);
  const setCoreState = useHARIKAStore((s) => s.setCoreState);
  const isVoiceActive = useHARIKAStore((s) => s.isVoiceActive);
  const setIsVoiceActive = useHARIKAStore((s) => s.setIsVoiceActive);
  const setInterimTranscript = useHARIKAStore((s) => s.setInterimTranscript);
  const addMessage = useHARIKAStore((s) => s.addMessage);
  const messages = useHARIKAStore((s) => s.messages);

  const isProcessing = coreState === 'processing';
  const isListening = coreState === 'listening' || isVoiceActive;

  const handleVoiceToggle = () => {
    if (isProcessing) return;

    if (isListening) {
      speechService.stop();
      setIsVoiceActive(false);
      setCoreState('idle');
      setInterimTranscript(null);
      return;
    }

    if (!speechService.isSupported()) {
      addMessage({
        sender: 'system',
        content: 'Speech recognition is not supported in this browser. Please use Chrome or Edge.',
      });
      return;
    }

    speechService.start({
      onStart: () => {
        setIsVoiceActive(true);
        setCoreState('listening');
        setInterimTranscript('Listening...');
      },
      onInterimResult: (transcript) => {
        setInterimTranscript(transcript || 'Listening...');
      },
      onFinalResult: async (transcript) => {
        setIsVoiceActive(false);
        setInterimTranscript(null);
        setCoreState('processing');

        const voiceText = transcript.trim();
        if (!voiceText) {
          setCoreState('idle');
          return;
        }

        // Post user voice transcript to canvas
        addMessage({
          sender: 'user',
          content: voiceText,
        });

        // Get user profile name
        const profile = userStorage.getProfile();
        const userName = profile?.name || 'User';

        // Format history
        const historyPayload = messages.map((m) => ({
          sender: m.sender,
          role: m.sender === 'user' ? 'user' : 'assistant',
          content: m.content,
        }));

        try {
          // Send to Cognition Engine API
          const data = await chatService.sendMessage(voiceText, userName, historyPayload);

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
            content: `Received voice input "${voiceText}", but the backend engine is currently offline or unreachable.`,
          });

          setTimeout(() => {
            setCoreState('idle');
          }, 2000);
        }
      },
      onError: (error) => {
        setIsVoiceActive(false);
        setInterimTranscript(null);
        setCoreState('idle');

        if (error.type === 'permission-denied') {
          addMessage({
            sender: 'system',
            content: 'Microphone permission was denied. Please allow microphone access in browser settings.',
          });
        } else if (error.type === 'unsupported') {
          addMessage({
            sender: 'system',
            content: 'Web Speech API is unsupported in this browser.',
          });
        } else if (error.type !== 'no-speech' && error.type !== 'aborted') {
          addMessage({
            sender: 'system',
            content: `Voice error: ${error.message}`,
          });
        }
      },
      onEnd: () => {
        setIsVoiceActive(false);
        setInterimTranscript(null);
        if (useHARIKAStore.getState().coreState === 'listening') {
          setCoreState('idle');
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
          ? 'Processing voice input...'
          : isListening
          ? 'Stop Voice Input'
          : 'Activate Push-to-Talk Voice Input'
      }
    >
      {isProcessing ? (
        <Loader2 className="w-4 h-4 animate-spin text-purple-400" />
      ) : isListening ? (
        <Mic className="w-4 h-4" />
      ) : (
        <MicOff className="w-4 h-4" />
      )}
    </button>
  );
};
