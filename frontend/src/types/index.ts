/**
 * Core AI Engine Visual Operational States
 */
export type CoreState =
  | 'booting'
  | 'idle'
  | 'listening'
  | 'processing'
  | 'speaking'
  | 'sleeping'
  | 'error';

export interface Message {
  id: string;
  sender: 'user' | 'harika' | 'system';
  content: string;
  timestamp: string;
  status?: 'sending' | 'delivered' | 'error';
}

export interface BackendHealthResponse {
  status: string;
  app_name: string;
  version: string;
  timestamp: string;
}

export interface SystemMetrics {
  status: string;
  cpu_usage_percent: number;
  memory_usage_percent: number;
  active_services: number;
}
