import { useState, useCallback } from 'react';
import api from '../services/api';
import { supabase } from '../services/supabase';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

interface ChatSession {
  session_id: string;
  last_message: string;
  messages_count: number;
  created_at: string;
  updated_at: string;
}

export function useChat() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

  const sendMessage = useCallback(async (text: string) => {
    // Add user message immediately
    const userMsg: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsStreaming(true);

    try {
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      const response = await fetch(`${process.env.EXPO_PUBLIC_API_URL}/chat/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          session_id: currentSessionId ?? undefined,
          message: text,
        }),
      });

      if (!response.ok) {
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: `Error: Server returned ${response.status}. Please try again.`,
          };
          return updated;
        });
        return;
      }

      let assistantContent = '';
      const assistantMsg: ChatMessage = {
        id: `temp-assistant-${Date.now()}`,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);

      const updateAssistant = (content: string) => {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === 'assistant') {
            updated[updated.length - 1] = { ...last, content };
          }
          return updated;
        });
      };

      const parseSseLines = (text: string) => {
        const lines = text.split('\n');
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'session_id') {
              setCurrentSessionId(data.value);
            } else if (data.type === 'token') {
              assistantContent += data.value;
              updateAssistant(assistantContent);
            }
          } catch {
            // Skip malformed lines
          }
        }
      };

      // Try streaming via ReadableStream (works on web), fall back to
      // reading the full response text (React Native / Hermes)
      const reader = response.body?.getReader?.();
      if (reader) {
        const decoder = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          parseSseLines(decoder.decode(value, { stream: true }));
        }
      } else {
        // React Native: ReadableStream not available — read full text
        const text = await response.text();
        parseSseLines(text);
      }
    } finally {
      setIsStreaming(false);
    }
  }, [currentSessionId]);

  const fetchSessions = useCallback(async () => {
    const { data } = await api.get('/chat/sessions');
    setSessions(data.sessions);
  }, []);

  const loadSession = useCallback(async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    // Reload messages for this session from the backend
    // For now, sessions are server-managed
    setMessages([]);
  }, []);

  const deleteSession = useCallback(async (sessionId: string) => {
    await api.delete(`/chat/sessions/${sessionId}`);
    setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
    if (currentSessionId === sessionId) {
      setCurrentSessionId(null);
      setMessages([]);
    }
  }, [currentSessionId]);

  const startNewSession = useCallback(() => {
    setCurrentSessionId(null);
    setMessages([]);
  }, []);

  return {
    sessions,
    messages,
    isStreaming,
    currentSessionId,
    sendMessage,
    fetchSessions,
    loadSession,
    deleteSession,
    startNewSession,
  };
}
