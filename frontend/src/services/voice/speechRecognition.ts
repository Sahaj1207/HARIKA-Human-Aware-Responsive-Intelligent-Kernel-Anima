import { VoiceCallbacks, SpeechRecognitionOptions, VoiceError } from './types';
import { detectBrowser } from './browser';

// SpeechRecognition global types declaration for Web Speech API
declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

export class SpeechRecognitionService {
  private recognition: any = null;
  private isListening: boolean = false;

  constructor() {
    this.initRecognition();
  }

  private initRecognition(): void {
    if (typeof window === 'undefined') return;
    const SpeechRecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognitionClass) {
      try {
        this.recognition = new SpeechRecognitionClass();
      } catch (e) {
        console.error('[HARIKA Voice Engine] Failed to instantiate SpeechRecognition:', e);
      }
    }
  }

  public isSupported(): boolean {
    if (!this.recognition) {
      this.initRecognition();
    }
    return !!this.recognition;
  }

  public start(callbacks: VoiceCallbacks, options: SpeechRecognitionOptions = {}): boolean {
    if (!this.isSupported()) {
      callbacks.onError?.({
        type: 'unsupported',
        message: 'Speech recognition is not supported in this browser. Please use Google Chrome for the best experience.',
      });
      return false;
    }

    // Reset previous instance if active
    if (this.isListening) {
      this.stop();
    }

    // Re-create instance to ensure fresh event handlers & state in WebKit browsers
    const SpeechRecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.recognition = new SpeechRecognitionClass();

    this.recognition.lang = options.lang || 'en-US';
    this.recognition.continuous = options.continuous ?? false;
    this.recognition.interimResults = options.interimResults ?? true;

    let finalTranscriptCaptured = false;

    this.recognition.onstart = () => {
      this.isListening = true;
      console.log('[HARIKA Voice Engine] SpeechRecognition started successfully.');
      callbacks.onStart?.();
    };

    this.recognition.onresult = (event: any) => {
      let interim = '';
      let final = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          final += transcript;
        } else {
          interim += transcript;
        }
      }

      if (interim) {
        callbacks.onInterimResult?.(interim);
      }

      if (final) {
        finalTranscriptCaptured = true;
        callbacks.onFinalResult?.(final.trim());
      }
    };

    this.recognition.onerror = (event: any) => {
      this.isListening = false;
      const rawError = event.error || 'unknown';

      console.error('[HARIKA Voice Engine] SpeechRecognition Error Event:', rawError, event);

      let error: VoiceError;

      switch (rawError) {
        case 'not-allowed':
        case 'service-not-allowed':
          error = {
            type: 'permission-denied',
            message: 'Microphone permission or speech recognition service was denied by the browser.',
          };
          break;
        case 'audio-capture':
          error = {
            type: 'unknown',
            message: 'Audio capture failed. Ensure your microphone is connected and not locked by another application.',
          };
          break;
        case 'network': {
          const browser = detectBrowser();
          const message = browser.isEdge
            ? 'Speech recognition is currently more reliable in Google Chrome. Please switch to Chrome for the best voice experience.'
            : 'Network error. Web Speech API requires internet connectivity to speech recognition servers.';
          error = {
            type: 'network',
            message,
          };
          break;
        }
        case 'no-speech':
          error = {
            type: 'no-speech',
            message: 'No speech was detected.',
          };
          break;
        case 'aborted':
          error = {
            type: 'aborted',
            message: 'Speech recognition was aborted.',
          };
          break;
        default:
          error = {
            type: 'unknown',
            message: `Speech recognition error: "${rawError}"`,
          };
          break;
      }

      callbacks.onError?.(error);
    };

    this.recognition.onend = () => {
      this.isListening = false;
      console.log('[HARIKA Voice Engine] SpeechRecognition session ended.');
      if (!finalTranscriptCaptured) {
        callbacks.onEnd?.();
      }
    };

    try {
      this.recognition.start();
      return true;
    } catch (err: any) {
      this.isListening = false;
      console.error('[HARIKA Voice Engine] Failed to invoke recognition.start():', err);
      callbacks.onError?.({
        type: 'unknown',
        message: `Failed to start voice input: ${err?.message || err || 'Recognition start error'}`,
      });
      return false;
    }
  }

  public stop(): void {
    if (this.recognition && this.isListening) {
      try {
        this.recognition.stop();
      } catch (err) {
        console.warn('[HARIKA Voice Engine] Warning during recognition.stop():', err);
      }
      this.isListening = false;
    }
  }
}

export const speechService = new SpeechRecognitionService();
