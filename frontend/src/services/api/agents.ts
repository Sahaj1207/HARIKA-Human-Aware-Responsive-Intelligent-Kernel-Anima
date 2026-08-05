import { apiClient } from './client';

export interface AgentStatusApi {
  agent_id: string;
  goal_id?: string;
  plan_id?: string;
  state: string;
  current_task?: string;
  progress_percent: number;
  running_duration_s: number;
  retries_count: number;
  completed_tasks_count: number;
  total_tasks_count: number;
  updated_at: string;
}

export interface AgentMetricsApi {
  agents_created: number;
  completed_count: number;
  failed_count: number;
  cancelled_count: number;
  average_duration_s: number;
  retry_rate_percent: number;
  success_rate_percent: number;
  average_tasks_per_agent: number;
}

export interface AgentHistoryItemApi {
  agent_id: string;
  goal_id?: string;
  plan_id?: string;
  tasks_count: number;
  duration_ms: number;
  result_summary: string;
  timestamp: string;
}

export const agentsService = {
  listActive: async (): Promise<AgentStatusApi[]> => {
    const res = await apiClient.get<AgentStatusApi[]>('/agents');
    return res.data;
  },

  getHistory: async (limit = 20): Promise<AgentHistoryItemApi[]> => {
    const res = await apiClient.get<AgentHistoryItemApi[]>(`/agents/history?limit=${limit}`);
    return res.data;
  },

  getMetrics: async (): Promise<AgentMetricsApi> => {
    const res = await apiClient.get<AgentMetricsApi>('/agents/metrics');
    return res.data;
  },

  startAgent: async (userMessage: string, goalId?: string): Promise<Record<string, unknown>> => {
    const res = await apiClient.post<Record<string, unknown>>('/agents/start', {
      user_message: userMessage,
      goal_id: goalId,
    });
    return res.data;
  },

  pauseAgent: async (agentId: string): Promise<AgentStatusApi> => {
    const res = await apiClient.post<AgentStatusApi>('/agents/pause', { agent_id: agentId });
    return res.data;
  },

  resumeAgent: async (agentId: string): Promise<AgentStatusApi> => {
    const res = await apiClient.post<AgentStatusApi>('/agents/resume', { agent_id: agentId });
    return res.data;
  },

  cancelAgent: async (agentId: string): Promise<AgentStatusApi> => {
    const res = await apiClient.post<AgentStatusApi>('/agents/cancel', { agent_id: agentId });
    return res.data;
  },
};
