import { useState, useEffect, useRef, useCallback } from 'react';

interface UseStreamingTextOptions {
  delayMs?: number;
  onComplete?: () => void;
}

export function useStreamingText(
  fullText: string,
  options: UseStreamingTextOptions = {}
) {
  const { delayMs = 30, onComplete } = options;
  const [displayedText, setDisplayedText] = useState('');
  const [isStreaming, setIsStreaming] = useState(true);
  const indexRef = useRef(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setDisplayedText(fullText);
    setIsStreaming(false);
    if (onComplete) onComplete();
  }, [fullText, onComplete]);

  useEffect(() => {
    setDisplayedText('');
    setIsStreaming(true);
    indexRef.current = 0;

    if (!fullText) {
      setIsStreaming(false);
      return;
    }

    timerRef.current = setInterval(() => {
      indexRef.current += 1;
      const nextChunk = fullText.slice(0, indexRef.current);
      setDisplayedText(nextChunk);

      if (indexRef.current >= fullText.length) {
        if (timerRef.current) clearInterval(timerRef.current);
        timerRef.current = null;
        setIsStreaming(false);
        if (onComplete) onComplete();
      }
    }, delayMs);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [fullText, delayMs, onComplete]);

  return { displayedText, isStreaming, stop };
}
