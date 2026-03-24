import { useCallback } from 'react';
import api from '../services/api';
import { supabase } from '../services/supabase';
import { useChatStore, ChatMessage } from '../stores/chatStore';

export function useChat() {
  const messages = useChatStore((s) => s.messages);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const currentSessionId = useChatStore((s) => s.currentSessionId);
  const sessions = useChatStore((s) => s.sessions);

  const addMessage = useChatStore((s) => s.addMessage);
  const updateLastAssistant = useChatStore((s) => s.updateLastAssistant);
  const setIsStreaming = useChatStore((s) => s.setIsStreaming);
  const setCurrentSessionId = useChatStore((s) => s.setCurrentSessionId);
  const setSessions = useChatStore((s) => s.setSessions);
  const removeSession = useChatStore((s) => s.removeSession);
  const clearMessages = useChatStore((s) => s.clearMessages);

  const sendMessage = useCallback(async (text: string) => {
    // Add user message immediately
    const userMsg: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    };
    addMessage(userMsg);
    setIsStreaming(true);

    try {
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;
      const chatUrl = `${process.env.EXPO_PUBLIC_API_URL}/chat/message`;

      console.log('[Chat] POST', chatUrl);
      console.log('[Chat] token:', token ? `${token.substring(0, 20)}...` : 'NONE');
      console.log('[Chat] session_id:', currentSessionId ?? 'new');

      const response = await fetch(chatUrl, {
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
        const errorBody = await response.text().catch(() => '');
        console.error(`[Chat] Error ${response.status}:`, errorBody);
        addMessage({
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: `Error: Server returned ${response.status}. Please try again.`,
          created_at: new Date().toISOString(),
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
      addMessage(assistantMsg);

      const parseSseLines = (sseText: string) => {
        const lines = sseText.split('\n');
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'session_id') {
              setCurrentSessionId(data.value);
            } else if (data.type === 'token') {
              assistantContent += data.value;
              updateLastAssistant(assistantContent);
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
        const fullText = await response.text();
        parseSseLines(fullText);
      }
    } finally {
      setIsStreaming(false);
    }
  }, [currentSessionId, addMessage, updateLastAssistant, setIsStreaming, setCurrentSessionId]);

  const fetchSessions = useCallback(async () => {
    const { data } = await api.get('/chat/sessions');
    setSessions(data.sessions);
  }, [setSessions]);

  const loadSession = useCallback(async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    // Reload messages for this session from the backend
    // For now, sessions are server-managed
    clearMessages();
    setCurrentSessionId(sessionId);
  }, [setCurrentSessionId, clearMessages]);

  const deleteSession = useCallback(async (sessionId: string) => {
    await api.delete(`/chat/sessions/${sessionId}`);
    removeSession(sessionId);
  }, [removeSession]);

  const startNewSession = useCallback(() => {
    clearMessages();
  }, [clearMessages]);

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
