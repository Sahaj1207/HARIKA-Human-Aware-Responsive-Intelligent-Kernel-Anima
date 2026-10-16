import React, { useState } from 'react';
import { Mic, Loader2 } from 'lucide-react';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { coreStateManager } from '@/services/coreState/coreStateManager';
import { errorDetail } from '@/services/api/llmSettings';
import { speechService } from '@/services/api/speech';
import { askHarika } from '@/components/apple/MessageList';

/**
 * Push-to-talk with HARIKA's own offline speech recognition: tap, speak, and
 * the request is sent as if typed (and the reply spoken, per Settings > Voice).
 */
export const VoiceButton: React.FC = () => {
  const coreState = useHARIKAStore((s) => s.coreState);
  const setInterimTranscript = useHARIKAStore((s) => s.setInterimTranscript);
  const addMessage = useHARIKAStore((s) => s.addMessage);
  const completeGeneration = useHARIKAStore((s) => s.completeGeneration);
  const [listening, setListening] = useState(false);

  const isProcessing = coreState === 'thinking' || coreState === 'speaking';

  const listen = async () => {
    if (isProcessing || listening) return;
    setListening(true);
    coreStateManager.transitionTo('listening');
    setInterimTranscript('Listening…');
    try {
      const text = (await speechService.listen()).trim();
      setInterimTranscript(null);
      completeGeneration();
      if (text) askHarika(text, { spoken: true });
    } catch (err) {
      setInterimTranscript(null);
      completeGeneration();
      addMessage({ role: 'system', content: errorDetail(err, "I couldn't use the microphone.") });
    } finally {
      setListening(false);
    }
  };

  return (
    <button
      type="button"
      onClick={() => void listen()}
      disabled={isProcessing}
      aria-pressed={listening}
      aria-label={listening ? 'Listening' : 'Speak to HARIKA'}
      title={listening ? 'Listening… stop talking to send' : 'Speak to HARIKA'}
      className={`w-8 h-8 grid place-items-center rounded-full shrink-0 transition-colors disabled:opacity-40 ${
        listening ? 'bg-danger text-white' : 'text-label-2 hover:text-label hover:bg-fill'
      }`}
    >
      {isProcessing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mic className="w-[18px] h-[18px]" strokeWidth={2.2} />}
    </button>
  );
};
