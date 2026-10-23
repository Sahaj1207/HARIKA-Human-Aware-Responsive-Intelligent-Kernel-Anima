import { create } from 'zustand';
import { CoreState, Message } from '@/types';
import { persistenceService } from '@/services/storage/persistence';
import { coreStateManager } from '@/services/coreState/coreStateManager';

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

  // Live step progress pushed by the backend ("Step 2/3: search F1 news")
  activity: string | null;
  setActivity: (activity: string | null) => void;

  /** Tone of HARIKA's latest reply ("cheerful", "calm"...); tints the orb, then fades back to warm. */
  mood: string;
  setMood: (mood: string) => void;
  /** A multi-step task is running and can be stopped. */
  taskRunning: boolean;
  setTaskRunning: (running: boolean) => void;

  // Panel State
  isQuickPanelOpen: boolean;
  toggleQuickPanel: () => void;

  // Spatial Conversation State
  messages: Message[];
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => string;
  updateMessageStatus: (id: string, status: Message['status']) => void;
  clearMessages: () => void;

  // Single Authoritative Function to reset ALL generation lifecycle state
  completeGeneration: () => void;
}

const MOOD_SECONDS = 30;
let moodTimer: ReturnType<typeof setTimeout> | undefined;

// A new conversation starts empty; the empty state greets the user.
const initialMessages = persistenceService.getMessages() || [];

export const useHARIKAStore = create<HARIKAStore>((set, get) => ({
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

  activity: null,
  setActivity: (activity) => set({ activity }),

  mood: 'warm',
  setMood: (mood) => {
    clearTimeout(moodTimer);
    set({ mood: mood || 'warm' });
    moodTimer = setTimeout(() => set({ mood: 'warm' }), MOOD_SECONDS * 1000);
  },
  taskRunning: false,
  setTaskRunning: (taskRunning) => set({ taskRunning }),

  isQuickPanelOpen: false,
  toggleQuickPanel: () => set((state) => ({ isQuickPanelOpen: !state.isQuickPanelOpen })),

  messages: initialMessages,

  addMessage: (msg) => {
    const newId = `msg-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`;
    
    // Explicitly resolve role with proper operator grouping
    const resolvedRole: 'user' | 'assistant' | 'system' =
      msg.role ? msg.role : ((msg as any).sender === 'user' ? 'user' : (msg as any).sender === 'system' ? 'system' : 'assistant');

    const newMsg: Message = {
      ...msg,
      id: newId,
      timestamp: new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }),
      role: resolvedRole,
      status: msg.status || 'completed',
      metadata: msg.metadata || {},
    };

    set((state) => {
      const updatedMessages = [...state.messages, newMsg];
      persistenceService.saveMessages(updatedMessages);
      return { messages: updatedMessages };
    });

    return newId;
  },

  updateMessageStatus: (id, status) => {
    set((state) => {
      const updatedMessages = state.messages.map((m) =>
        m.id === id ? { ...m, status } : m
      );
      persistenceService.saveMessages(updatedMessages);
      return { messages: updatedMessages };
    });
  },

  clearMessages: () => {
    persistenceService.clearMessages();
    set({ messages: [] });
  },

  completeGeneration: () => {
    const state = get();
    const handler = state.stopStreamingHandler;

    set({
      stopStreamingHandler: null,
      isStreaming: false,
      thinkingStage: 'idle',
    });

    if (handler) {
      try {
        handler();
      } catch {
        // ignore
      }
    }

    const updatedMessages = state.messages.map((m) =>
      m.status === 'streaming' ? { ...m, status: 'completed' as const } : m
    );

    set({ messages: updatedMessages });
    persistenceService.saveMessages(updatedMessages);
    coreStateManager.transitionTo('idle');
  },
}));
