import { apiClient } from './client';

export interface PresenceStatusApi {
  status: string;
  engine: string;
  overall_score: number;
  loop_running: boolean;
}

export interface PresenceStateApi {
  current_topic?: string;
  current_goal?: string;
  current_task?: string;
  current_project?: string;
  conversation_mode: string;
  recent_entities: Array<{ entity: string; attribute: string; value: unknown; confidence: number }>;
  recent_corrections: Array<Record<string, unknown>>;
}

export interface PresenceScoreApi {
  awareness: number;
  continuity: number;
  verification: number;
  initiative_quality: number;
  correction_recovery: number;
  memory_quality: number;
  attention_stability: number;
  overall_score: number;
}

export const presenceService = {
  getStatus: async (): Promise<PresenceStatusApi> => {
    const res = await apiClient.get<PresenceStatusApi>('/presence/status');
    return res.data;
  },

  getState: async (): Promise<PresenceStateApi> => {
    const res = await apiClient.get<PresenceStateApi>('/presence/state');
    return res.data;
  },

  getWorkingMemory: async (): Promise<Record<string, unknown>> => {
    const res = await apiClient.get<Record<string, unknown>>('/presence/working_memory');
    return res.data;
  },

  getScore: async (): Promise<PresenceScoreApi> => {
    const res = await apiClient.get<PresenceScoreApi>('/presence/score');
    return res.data;
  },
};
