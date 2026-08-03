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
};
