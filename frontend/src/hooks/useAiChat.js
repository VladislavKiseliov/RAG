import { useState, useCallback, useRef } from 'react';
import { ENDPOINTS } from '../config/api';

const GREETING = { id: 'greeting', content: 'Привет! Я ваш помощник по документации. Задайте вопрос.', role: 'assistant' };

const genId = () =>
    typeof crypto?.randomUUID === 'function'
        ? crypto.randomUUID()
        : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;

export function useAiChat(api, showError) {
    const [messages, setMessages] = useState([GREETING]);
    const [isTyping, setIsTyping] = useState(false);
    const [currentConversationId, setCurrentConversationId] = useState(null);
    const [conversations, setConversations] = useState([]);
    const historyAbortRef = useRef(null);

    const loadUserConversations = useCallback(async () => {
        try {
            const data = await api.get(ENDPOINTS.CONVERSATIONS);
            setConversations(data.conversations || []);
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError]);

    const loadConversationHistory = useCallback(async (conversationId) => {
        historyAbortRef.current?.abort();
        const controller = new AbortController();
        historyAbortRef.current = controller;
        try {
            const data = await api.get(`/api/chats/${conversationId}`, { signal: controller.signal });
            const formatted = data.history.map((msg) => ({
                id: msg.id,
                content: msg.content,
                role: msg.role,
                sources: msg.sources || null,
            }));
            setMessages(formatted.length === 0 ? [GREETING] : formatted);
        } catch (e) {
            if (e.name === 'AbortError') return;
            setMessages([GREETING]);
        }
    }, [api]);

    const resetMessages = useCallback(() => {
        historyAbortRef.current?.abort();
        setMessages([GREETING]);
    }, []);

    const abortHistory = useCallback(() => {
        historyAbortRef.current?.abort();
    }, []);

    const sendAiMessage = useCallback(async (text, conversationId) => {
        let convId = conversationId;
        if (!convId) {
            try {
                const data = await api.post(ENDPOINTS.CONVERSATIONS);
                convId = data.conversation_id;
                setCurrentConversationId(convId);
                setMessages([GREETING]);
                loadUserConversations();
            } catch (e) {
                showError(e.message);
                return;
            }
        }

        setMessages((prev) => [...prev, { id: genId(), content: text, role: 'user' }]);
        setIsTyping(true);

        try {
            const data = await api.post(ENDPOINTS.MESSAGES(convId), { user_message: text });
            setMessages((prev) => [...prev, {
                id: genId(),
                content: data.response,
                role: 'assistant',
                sources: data.sources || null,
            }]);
        } catch (e) {
            showError(e.message);
            setMessages((prev) => [...prev, {
                id: genId(),
                content: 'Произошла ошибка при получении ответа.',
                role: 'assistant',
            }]);
        } finally {
            setIsTyping(false);
        }
    }, [api, loadUserConversations, showError]);

    const removeConversation = useCallback(
        (id) => setConversations((prev) => prev.filter((c) => c.chat_guid !== id)),
        []
    );

    const renameConversation = useCallback(
        (id, title) => setConversations((prev) => prev.map((c) => (c.chat_guid === id ? { ...c, title } : c))),
        []
    );

    return {
        messages,
        isTyping,
        currentConversationId,
        setCurrentConversationId,
        conversations,
        loadUserConversations,
        loadConversationHistory,
        resetMessages,
        abortHistory,
        sendAiMessage,
        removeConversation,
        renameConversation,
    };
}