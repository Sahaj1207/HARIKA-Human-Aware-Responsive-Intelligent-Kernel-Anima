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
      timeout: 60000, // Explicit 60s timeout for LLM response generation
    });

    return response.data;
  },
};
