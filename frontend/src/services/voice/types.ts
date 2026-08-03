export type VoiceStatus = 'idle' | 'listening' | 'processing' | 'error';

export interface VoiceError {
  type: 'unsupported' | 'permission-denied' | 'no-speech' | 'network' | 'aborted' | 'unknown';
  message: string;
}

export interface VoiceCallbacks {
  onStart?: () => void;
  onInterimResult?: (transcript: string) => void;
  onFinalResult?: (transcript: string) => void;
  onError?: (error: VoiceError) => void;
  onEnd?: () => void;
}

export interface SpeechRecognitionOptions {
  lang?: string;
  continuous?: boolean;
  interimResults?: boolean;
}
