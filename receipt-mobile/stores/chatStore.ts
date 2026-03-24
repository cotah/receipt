import { create } from 'zustand';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export interface ChatSession {
  session_id: string;
  last_message: string;
  messages_count: number;
  created_at: string;
  updated_at: string;
}

interface ChatState {
  sessions: ChatSession[];
  messages: ChatMessage[];
  isStreaming: boolean;
  currentSessionId: string | null;

  addMessage: (msg: ChatMessage) => void;
  updateLastAssistant: (content: string) => void;
  setIsStreaming: (v: boolean) => void;
  setCurrentSessionId: (id: string | null) => void;
  setSessions: (s: ChatSession[]) => void;
  removeSession: (id: string) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  sessions: [],
  messages: [],
  isStreaming: false,
  currentSessionId: null,

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

  updateLastAssistant: (content) =>
    set((s) => {
      const updated = [...s.messages];
      const last = updated[updated.length - 1];
      if (last && last.role === 'assistant') {
        updated[updated.length - 1] = { ...last, content };
      }
      return { messages: updated };
    }),

  setIsStreaming: (v) => set({ isStreaming: v }),
  setCurrentSessionId: (id) => set({ currentSessionId: id }),
  setSessions: (sessions) => set({ sessions }),
  removeSession: (id) =>
    set((s) => ({
      sessions: s.sessions.filter((sess) => sess.session_id !== id),
      ...(s.currentSessionId === id ? { currentSessionId: null, messages: [] } : {}),
    })),
  clearMessages: () => set({ messages: [], currentSessionId: null }),
}));
