import { useState, useEffect, useRef, useCallback } from 'react';

interface UseStreamingTextOptions {
  delayMs?: number;
  onComplete?: () => void;
}

export function useStreamingText(
  fullText: string,
  options: UseStreamingTextOptions = {}
) {
  const { delayMs = 25, onComplete } = options;
  const [displayedText, setDisplayedText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const indexRef = useRef(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const onCompleteRef = useRef(onComplete);

  // Keep onComplete ref updated without triggering effect re-subscriptions
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setDisplayedText(fullText);
    setIsStreaming(false);
  }, [fullText]);

  useEffect(() => {
    if (!fullText) {
      setDisplayedText('');
      setIsStreaming(false);
      return;
    }

    setDisplayedText('');
    setIsStreaming(true);
    indexRef.current = 0;

    timerRef.current = setInterval(() => {
      indexRef.current += 1;
      if (indexRef.current >= fullText.length) {
        if (timerRef.current) {
          clearInterval(timerRef.current);
          timerRef.current = null;
        }
        setDisplayedText(fullText);
        setIsStreaming(false);
        if (onCompleteRef.current) {
          onCompleteRef.current();
        }
      } else {
        setDisplayedText(fullText.slice(0, indexRef.current));
      }
    }, delayMs);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [fullText, delayMs]);

  return { displayedText, isStreaming, stop };
}
