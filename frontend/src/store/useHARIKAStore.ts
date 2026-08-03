import { create } from 'zustand';
import { CoreState, Message } from '@/types';

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
  toggleVoice: () => void;
  isQuickPanelOpen: boolean;
  toggleQuickPanel: () => void;

  // Spatial Conversation State
  messages: Message[];
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void;
  clearMessages: () => void;
}

export const useHARIKAStore = create<HARIKAStore>((set) => ({
  coreState: 'booting',
  setCoreState: (coreState) => set({ coreState }),

  isBooted: false,
  isOnline: false,
  setIsBooted: (isBooted) => set({ isBooted }),
  setIsOnline: (isOnline) => set({ isOnline }),

  isVoiceActive: false,
  toggleVoice: () => set((state) => ({ isVoiceActive: !state.isVoiceActive })),

  isQuickPanelOpen: false,
  toggleQuickPanel: () => set((state) => ({ isQuickPanelOpen: !state.isQuickPanelOpen })),

  messages: [
    {
      id: 'welcome-1',
      sender: 'harika',
      content: 'HARIKA AI Operating System online. Systems initialized.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ],

  addMessage: (msg) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          ...msg,
          id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ],
    })),

  clearMessages: () => set({ messages: [] }),
}));
