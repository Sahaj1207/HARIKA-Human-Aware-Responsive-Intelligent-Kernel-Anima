import { Message, SessionData } from '@/types';

const KEYS = {
  USER: 'harika_user',
  MESSAGES: 'harika_messages',
  SESSION: 'harika_session',
} as const;

export const persistenceService = {
  // Messages persistence
  getMessages(): Message[] | null {
    try {
      const data = localStorage.getItem(KEYS.MESSAGES);
      return data ? (JSON.parse(data) as Message[]) : null;
    } catch {
      return null;
    }
  },

  saveMessages(messages: Message[]): void {
    try {
      localStorage.setItem(KEYS.MESSAGES, JSON.stringify(messages));
    } catch (e) {
      console.error('[Persistence] Failed to save messages:', e);
    }
  },

  clearMessages(): void {
    localStorage.removeItem(KEYS.MESSAGES);
  },

  // Session persistence
  getSession(): SessionData | null {
    try {
      const data = localStorage.getItem(KEYS.SESSION);
      return data ? (JSON.parse(data) as SessionData) : null;
    } catch {
      return null;
    }
  },

  saveSession(session: SessionData): void {
    try {
      localStorage.setItem(KEYS.SESSION, JSON.stringify(session));
    } catch (e) {
      console.error('[Persistence] Failed to save session:', e);
    }
  },
};
