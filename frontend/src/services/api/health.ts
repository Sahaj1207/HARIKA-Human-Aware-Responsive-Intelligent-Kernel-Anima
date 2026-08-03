import { apiClient } from './client';
import { BackendHealthResponse, SystemMetrics } from '@/types';

export const healthService = {
  async checkHealth(): Promise<BackendHealthResponse> {
    const response = await apiClient.get<BackendHealthResponse>('/health');
    return response.data;
  },

  async getMetrics(): Promise<SystemMetrics> {
    const response = await apiClient.get<SystemMetrics>('/metrics');
    return response.data;
  },
};
