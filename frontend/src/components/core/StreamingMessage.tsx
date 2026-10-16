import React, { useEffect, useRef, useCallback } from 'react';
import { useStreamingText } from '@/hooks/useStreamingText';
import { useHARIKAStore } from '@/store/useHARIKAStore';

interface StreamingMessageProps {
  messageId: string;
  content: string;
  onComplete?: () => void;
}

export const StreamingMessage: React.FC<StreamingMessageProps> = ({
  content,
  onComplete,
}) => {
  const completeGeneration = useHARIKAStore((s) => s.completeGeneration);
  const setStopStreamingHandler = useHARIKAStore((s) => s.setStopStreamingHandler);
  const setIsStreaming = useHARIKAStore((s) => s.setIsStreaming);
  const hasCompletedRef = useRef(false);

  const handleStreamComplete = useCallback(() => {
    if (hasCompletedRef.current) return;
    hasCompletedRef.current = true;
    completeGeneration();
    if (onComplete) onComplete();
  }, [completeGeneration, onComplete]);

  const { displayedText, isStreaming, stop } = useStreamingText(content, {
    delayMs: 18,
    onComplete: handleStreamComplete,
  });

  const handleStop = useCallback(() => {
    if (hasCompletedRef.current) return;
    hasCompletedRef.current = true;
    stop();
    completeGeneration();
  }, [stop, completeGeneration]);

  useEffect(() => {
    setIsStreaming(true);
    setStopStreamingHandler(() => handleStop);

    return () => {
      setStopStreamingHandler(null);
    };
  }, [handleStop, setIsStreaming, setStopStreamingHandler]);

  return (
    <span>
      {displayedText}
      {isStreaming && <span className="inline-block ml-0.5 w-[2px] h-[1.05em] align-[-0.15em] bg-current opacity-50 animate-pulse" />}
    </span>
  );
};
