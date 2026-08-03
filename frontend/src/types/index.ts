/**
 * Core AI Engine Visual Operational States
 */
export type CoreState =
  | 'booting'
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'sleeping'
  | 'error';

export interface MessageMetadata {
  provider?: string;
  model?: string;
  latency_ms?: number;
  [key: string]: any;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  status?: 'sending' | 'delivered' | 'streaming' | 'completed' | 'error';
  metadata?: MessageMetadata;
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

export interface SessionData {
  scrollPosition: number;
  lastActive: string;
}
