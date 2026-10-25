import { apiClient } from './client';

export interface MemoryItemApi {
  id: string;
  category: string;
  title: string;
  content: string;
  importance: number;
  confidence: number;
  source: string;
  tags: string[];
  version: number;
  revision: number;
  deleted: boolean;
  created_at: string;
  updated_at: string;
  last_accessed: string;
}

export interface MemoryMetricsApi {
  total_memories: number;
  categories_count: Record<string, number>;
  deleted_count: number;
  average_importance: number;
  average_confidence: number;
  latest_update: string;
  storage_bytes: number;
}

export interface CreateMemoryPayload {
  category: string;
  title: string;
  content: string;
  importance?: number;
  confidence?: number;
  tags?: string[];
}

export interface MemorySettings {
  /** Keep a journal of conversations on this computer (for recall, day summaries and habits). */
  remember_conversations: boolean;
  /** Mention things you usually ask for at about this time. */
  notice_habits: boolean;
}

export interface Habit {
  id: string;
  description: string;
  times: number;
}

/** Everything shown in Settings > Memory. */
export interface MemoryOverview {
  settings: MemorySettings;
  retention_days: number;
  journal_days: number;
  journal_since: string | null;
  facts: MemoryItemApi[];
  days: MemoryItemApi[];
  habits: Habit[];
  /** What HARIKA has learned from the music and videos played on this computer. */
  listening: { learn: boolean; plays: number; hours: number; top_artists: string[] };
}

export const memoryService = {
  async getMemories(query?: string, category?: string): Promise<MemoryItemApi[]> {
    const params: Record<string, string> = {};
    if (query) params.query = query;
    if (category) params.category = category;

    const response = await apiClient.get<MemoryItemApi[]>('/memory', { params });
    return response.data;
  },

  async getMetrics(): Promise<MemoryMetricsApi> {
    const response = await apiClient.get<MemoryMetricsApi>('/memory/metrics');
    return response.data;
  },

  async createMemory(payload: CreateMemoryPayload): Promise<MemoryItemApi> {
    const response = await apiClient.post<MemoryItemApi>('/memory', payload);
    return response.data;
  },

  async deleteMemory(id: string): Promise<void> {
    await apiClient.delete(`/memory/${id}`);
  },

  async clearAll(): Promise<void> {
    await apiClient.delete('/memory');
  },

  async overview(): Promise<MemoryOverview> {
    return (await apiClient.get<MemoryOverview>('/memory/overview')).data;
  },

  async update(changes: Partial<MemorySettings> & { learn_listening?: boolean }): Promise<MemoryOverview> {
    return (await apiClient.put<MemoryOverview>('/memory/settings', changes)).data;
  },

  /** Removes a memory for good (deleteMemory only hides it). */
  async forget(id: string): Promise<MemoryOverview> {
    return (await apiClient.delete<MemoryOverview>(`/memory/item/${encodeURIComponent(id)}`)).data;
  },

  async dismissHabit(id: string): Promise<MemoryOverview> {
    return (await apiClient.delete<MemoryOverview>(`/memory/habits/${encodeURIComponent(id)}`)).data;
  },

  async forgetListening(): Promise<MemoryOverview> {
    return (await apiClient.post<MemoryOverview>('/memory/forget-listening')).data;
  },

  async forgetEverything(): Promise<MemoryOverview> {
    return (await apiClient.post<MemoryOverview>('/memory/forget-everything')).data;
  },
};
