import { apiClient } from './client';

export interface VoiceStatusApi {
  status: string;
  state: string;
  speaker: {
    status: string;
    provider: string;
    ready: boolean;
  };
  transcriber: {
    status: string;
    provider: string;
    ready: boolean;
  };
}

export interface VoiceMetricsApi {
  total_sessions: number;
  average_duration_s: number;
  total_interruptions: number;
  average_recognition_latency_ms: number;
  average_speech_latency_ms: number;
  average_e2e_latency_ms: number;
}

export interface VoiceHistoryItemApi {
  session_id: string;
  duration_s: number;
  turns_count: number;
  commands_count: number;
  interruptions_count: number;
  summary: string;
  timestamp: string;
}

export const voiceEngineService = {
  getStatus: async (): Promise<VoiceStatusApi> => {
    const res = await apiClient.get<VoiceStatusApi>('/voice');
    return res.data;
  },

  getHistory: async (limit = 20): Promise<VoiceHistoryItemApi[]> => {
    const res = await apiClient.get<VoiceHistoryItemApi[]>(`/voice/history?limit=${limit}`);
    return res.data;
  },

  getMetrics: async (): Promise<VoiceMetricsApi> => {
    const res = await apiClient.get<VoiceMetricsApi>('/voice/metrics');
    return res.data;
  },

  startSession: async (continuous = false): Promise<Record<string, unknown>> => {
    const res = await apiClient.post<Record<string, unknown>>('/voice/start', { continuous });
    return res.data;
  },

  stopSession: async (): Promise<Record<string, unknown>> => {
    const res = await apiClient.post<Record<string, unknown>>('/voice/stop');
    return res.data;
  },

  triggerInterruption: async (): Promise<Record<string, unknown>> => {
    const res = await apiClient.post<Record<string, unknown>>('/voice/interruption');
    return res.data;
  },

  processDirective: async (text: string): Promise<Record<string, unknown>> => {
    const res = await apiClient.post<Record<string, unknown>>('/voice/directive', { voice_text: text });
    return res.data;
  },
};
