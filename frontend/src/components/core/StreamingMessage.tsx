import React, { useEffect } from 'react';
import { useStreamingText } from '@/hooks/useStreamingText';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { coreStateManager } from '@/services/coreState/coreStateManager';

interface StreamingMessageProps {
  content: string;
  onComplete?: () => void;
}

export const StreamingMessage: React.FC<StreamingMessageProps> = ({ content, onComplete }) => {
  const setStopStreamingHandler = useHARIKAStore((s) => s.setStopStreamingHandler);
  const setIsStreaming = useHARIKAStore((s) => s.setIsStreaming);

  const handleStreamComplete = () => {
    setIsStreaming(false);
    setStopStreamingHandler(null);
    coreStateManager.transitionTo('idle');
    if (onComplete) onComplete();
  };

  const { displayedText, isStreaming, stop } = useStreamingText(content, {
    delayMs: 25,
    onComplete: handleStreamComplete,
  });

  useEffect(() => {
    setIsStreaming(true);
    setStopStreamingHandler(() => stop);

    return () => {
      setStopStreamingHandler(null);
      setIsStreaming(false);
    };
  }, [stop, setIsStreaming, setStopStreamingHandler]);

  return (
    <div className="relative font-sans text-sm text-slate-100 leading-relaxed">
      <span>{displayedText}</span>
      {isStreaming && (
        <span className="inline-block ml-0.5 w-2 h-4 bg-cyan-400 animate-pulse align-middle" />
      )}
    </div>
  );
};
