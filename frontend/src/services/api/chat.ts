import { apiClient } from './client';

export interface ChatApiRequest {
  message: string;
  user_name?: string;
  conversation_history?: Array<{ sender?: string; role?: string; content: string }>;
  /** The message came from speech recognition (words may be misheard). */
  spoken?: boolean;
}

export interface ChatApiResponse {
  response: string;
  provider: string;
  model: string;
  latency_ms: number;
  /** How the reply should sound: warm, cheerful, empathetic, ... */
  tone?: string;
  /** Facts about the user HARIKA kept from this message. */
  learned?: string[];
}

/** Stops a running multi-step task between steps. */
export async function stopTask(): Promise<void> {
  await apiClient.post('/tasks/stop');
}

export const chatService = {
  async sendMessage(
    message: string,
    userName?: string,
    history?: Array<{ sender?: string; role?: string; content: string }>,
    spoken = false
  ): Promise<ChatApiResponse> {
    const payload: ChatApiRequest = {
      message,
      user_name: userName || 'User',
      conversation_history: history || [],
      spoken,
    };

    const response = await apiClient.post<ChatApiResponse>('/chat', payload, {
      timeout: 600000, // multi-step tasks on a local CPU model can take several minutes
    });

    return response.data;
  },
};
