import { create } from 'zustand';
import { CoreState, Message } from '@/types';
import { persistenceService } from '@/services/storage/persistence';

interface HARIKAStore {
  // Core Engine State
  coreState: CoreState;
  setCoreState: (state: CoreState) => void;

  // Connection & Boot State
  isBooted: boolean;
  isOnline: boolean;
  setIsBooted: (booted: boolean) => void;
  setIsOnline: (online: boolean) => void;

  // Interaction State
  isVoiceActive: boolean;
  setIsVoiceActive: (active: boolean) => void;
  toggleVoice: () => void;

  // Interim Speech Transcript State
  interimTranscript: string | null;
  setInterimTranscript: (transcript: string | null) => void;

  // Streaming & Generation State
  isStreaming: boolean;
  setIsStreaming: (streaming: boolean) => void;
  thinkingStage: 'idle' | 'thinking' | 'still-thinking';
  setThinkingStage: (stage: 'idle' | 'thinking' | 'still-thinking') => void;
  stopStreamingHandler: (() => void) | null;
  setStopStreamingHandler: (handler: (() => void) | null) => void;

  // Panel State
  isQuickPanelOpen: boolean;
  toggleQuickPanel: () => void;

  // Spatial Conversation State
  messages: Message[];
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void;
  clearMessages: () => void;
}

const defaultWelcomeMessage: Message = {
  id: 'welcome-1',
  role: 'assistant',
  content: 'HARIKA AI Operating System online. Systems initialized.',
  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  status: 'completed',
  metadata: { provider: 'system', model: 'harika-v0.2' },
};

const initialMessages = persistenceService.getMessages() || [defaultWelcomeMessage];

export const useHARIKAStore = create<HARIKAStore>((set) => ({
  coreState: 'booting',
  setCoreState: (coreState) => set({ coreState }),

  isBooted: false,
  isOnline: false,
  setIsBooted: (isBooted) => set({ isBooted }),
  setIsOnline: (isOnline) => set({ isOnline }),

  isVoiceActive: false,
  setIsVoiceActive: (isVoiceActive) => set({ isVoiceActive }),
  toggleVoice: () => set((state) => ({ isVoiceActive: !state.isVoiceActive })),

  interimTranscript: null,
  setInterimTranscript: (interimTranscript) => set({ interimTranscript }),

  isStreaming: false,
  setIsStreaming: (isStreaming) => set({ isStreaming }),

  thinkingStage: 'idle',
  setThinkingStage: (thinkingStage) => set({ thinkingStage }),

  stopStreamingHandler: null,
  setStopStreamingHandler: (stopStreamingHandler) => set({ stopStreamingHandler }),

  isQuickPanelOpen: false,
  toggleQuickPanel: () => set((state) => ({ isQuickPanelOpen: !state.isQuickPanelOpen })),

  messages: initialMessages,

  addMessage: (msg) =>
    set((state) => {
      const newMsg: Message = {
        ...msg,
        id: `msg-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        role: (msg.role || (msg as any).sender === 'user' ? 'user' : 'assistant') as any,
        status: msg.status || 'completed',
        metadata: msg.metadata || {},
      };
      const updatedMessages = [...state.messages, newMsg];
      persistenceService.saveMessages(updatedMessages);
      return { messages: updatedMessages };
    }),

  clearMessages: () => {
    persistenceService.clearMessages();
    set({ messages: [] });
  },
}));
