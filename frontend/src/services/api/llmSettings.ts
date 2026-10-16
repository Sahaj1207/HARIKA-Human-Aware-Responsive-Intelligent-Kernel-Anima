import { apiClient } from './client';

export type Role = 'understanding' | 'conversation';

export interface RoleChoice {
  service: string;
  model: string;
  on_device: boolean;
}

export interface LLMService {
  id: string;
  name: string;
  on_device: boolean;
  needs_key: boolean;
  sign_in: boolean;
  key_url: string;
  blurb: string;
  connected: boolean;
}

export interface LLMSettings {
  roles: Record<Role, RoleChoice>;
  services: LLMService[];
}

export interface LocalModelStatus {
  running: boolean;
  models: string[];
  recommended: { model: string; size: string; reason: string };
  has_recommended: boolean;
  downloading: boolean;
}

export interface ModelList {
  models: string[];
  suggested: Record<Role, string>;
}

/** Reads the backend's error detail so the UI can say what went wrong. */
export function errorDetail(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
}

export const llmSettingsService = {
  async get(): Promise<LLMSettings> {
    return (await apiClient.get<LLMSettings>('/settings/llm')).data;
  },
  async models(serviceId: string): Promise<ModelList> {
    return (await apiClient.get<ModelList>(`/settings/llm/services/${serviceId}/models`)).data;
  },
  async connect(serviceId: string, apiKey: string): Promise<ModelList> {
    return (await apiClient.put<ModelList>(`/settings/llm/services/${serviceId}/key`, { api_key: apiKey })).data;
  },
  async disconnect(serviceId: string): Promise<LLMSettings> {
    return (await apiClient.delete<LLMSettings>(`/settings/llm/services/${serviceId}/key`)).data;
  },
  async choose(role: Role, service: string, model: string): Promise<LLMSettings> {
    return (await apiClient.put<LLMSettings>(`/settings/llm/roles/${role}`, { service, model })).data;
  },
  async test(role: Role): Promise<{ ok: boolean; reply: string; model: string; latency_ms: number }> {
    return (await apiClient.post(`/settings/llm/roles/${role}/test`)).data;
  },
  /** Opens OpenRouter's sign-in page in the default browser. */
  async signInWithOpenRouter(): Promise<void> {
    await apiClient.get('/settings/llm/openrouter/start', { params: { open_browser: true } });
  },
  async localStatus(): Promise<LocalModelStatus> {
    return (await apiClient.get<LocalModelStatus>('/settings/llm/local/status')).data;
  },
  async downloadLocalModel(model: string): Promise<void> {
    await apiClient.post('/settings/llm/local/download', { model });
  },
  /** Opens an on-device service's download page (e.g. Ollama) in the default browser. */
  async openSetupPage(serviceId: string): Promise<void> {
    await apiClient.post(`/settings/llm/services/${serviceId}/open-setup-page`);
  },
  /** Opens the service's "create API key" page in the default browser. */
  async openKeyPage(serviceId: string): Promise<void> {
    await apiClient.post(`/settings/llm/services/${serviceId}/open-key-page`);
  },
};
