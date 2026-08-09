import { apiClient } from './client';

export interface RouterStatusApi {
  status: string;
  engine: string;
  total_requests: number;
  average_routing_latency_ms: number;
  routing_accuracy: number;
}

export interface RouterMetricsApi {
  total_requests: number;
  intent_frequencies: Record<string, number>;
  average_routing_latency_ms: number;
  routing_accuracy: number;
  clarification_rate: number;
  fallback_rate: number;
  tool_success_rate: number;
  memory_hit_rate: number;
}

export interface RouterDecisionItemApi {
  decision_id: string;
  timestamp: string;
  request: string;
  chosen_engine: string;
  chosen_action?: string;
  reason: string;
  confidence: number;
  policy: string;
  execution_time_ms: number;
  formatter_used: string;
  success: boolean;

}

export const routerEngineService = {
  getStatus: async (): Promise<RouterStatusApi> => {
    const res = await apiClient.get<RouterStatusApi>('/router');
    return res.data;
  },

  getHistory: async (limit = 20): Promise<RouterDecisionItemApi[]> => {
    const res = await apiClient.get<RouterDecisionItemApi[]>(`/router/history?limit=${limit}`);
    return res.data;
  },

  getMetrics: async (): Promise<RouterMetricsApi> => {
    const res = await apiClient.get<RouterMetricsApi>('/router/metrics');
    return res.data;
  },

  simulate: async (message: string): Promise<Record<string, unknown>> => {
    const res = await apiClient.post<Record<string, unknown>>('/router/simulate', { message });
    return res.data;
  },
};
