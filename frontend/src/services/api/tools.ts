import { apiClient } from './client';

export interface ToolManifestApi {
  name: string;
  display_name: string;
  description: string;
  version: string;
  category: string;
  permissions: string;
  enabled: boolean;
  platforms: string[];
}

export interface ToolExecutionHistoryApi {
  execution_id: string;
  success: boolean;
  status_code: string;
  tool_name: string;
  execution_time_ms: number;
  output?: any;
  error?: string;
  tool_version: string;
  api_version: string;
  timestamp: string;
}

export interface ToolMetricsApi {
  total_tools: number;
  enabled_tools: number;
  total_executions: number;
  success_rate: number;
  failure_rate: number;
  average_duration_ms: number;
  most_used_tool?: string;
}

export const toolsService = {
  async getTools(): Promise<ToolManifestApi[]> {
    const response = await apiClient.get<ToolManifestApi[]>('/tools');
    return response.data;
  },

  async getHistory(limit: number = 20): Promise<ToolExecutionHistoryApi[]> {
    const response = await apiClient.get<ToolExecutionHistoryApi[]>('/tools/history', {
      params: { limit },
    });
    return response.data;
  },

  async getMetrics(): Promise<ToolMetricsApi> {
    const response = await apiClient.get<ToolMetricsApi>('/tools/metrics');
    return response.data;
  },

  async toggleTool(name: string, enabled: boolean): Promise<void> {
    await apiClient.put(`/tools/${name}/toggle`, { enabled });
  },

  async executeTool(tool_name: string, args: Record<string, any> = {}, dry_run = false): Promise<ToolExecutionHistoryApi> {
    const response = await apiClient.post<ToolExecutionHistoryApi>('/tools/execute', {
      tool_name,
      arguments: args,
      dry_run,
    });
    return response.data;
  },
};
