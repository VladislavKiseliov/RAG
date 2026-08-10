import { useState, useCallback, useRef } from 'react';
import { ENDPOINTS } from '../config/api';

const GREETING = { id: 'greeting', content: 'Привет! Я ваш помощник по документации. Задайте вопрос.', role: 'assistant' };

const genId = () =>
    typeof crypto?.randomUUID === 'function'
        ? crypto.randomUUID()
        : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;

function parseSseEvent(rawEvent) {
    let eventName = 'message';
    let dataLine = '';
    for (const line of rawEvent.split('\n')) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim();
        else if (line.startsWith('data:')) dataLine = line.slice(5).trim();
    }
    return { eventName, data: dataLine ? JSON.parse(dataLine) : {} };
}

// Текст рядом с индикатором "печатает" по стадии из SSE-события status (см.
// llm_service/application/agent/agent_stream.py) - "retrieve" приходит дважды,
// если reflect_node запросил уточняющий поиск, поэтому различаем по счётчику.
function stageLabel(stage, retrieveEventCount) {
    if (stage === 'plan') return 'Думаю над вопросом…';
    if (stage === 'retrieve') return retrieveEventCount > 1 ? 'Уточняю поиск…' : 'Ищу в базе знаний…';
    return null;
}

export function useAiChat(api, showError) {
    const [messages, setMessages] = useState([GREETING]);
    const [isTyping, setIsTyping] = useState(false);
    const [typingLabel, setTypingLabel] = useState(null);
    // isTyping — только для «печатает…» (пока не пришёл первый токен), isStreaming
    // держит инпут задизейбленным на весь ответ, включая уже начавшийся стриминг текста.
    const [isStreaming, setIsStreaming] = useState(false);
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
            showError(e.message);
            setMessages([GREETING]);
        }
    }, [api, showError]);

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
        setIsStreaming(true);
        setTypingLabel(null);

        const assistantId = genId();
        let appended = false;
        let retrieveEventCount = 0;

        try {
            const stream = await api.postStream(ENDPOINTS.MESSAGES_STREAM(convId), { user_message: text });
            const reader = stream.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });

                let sepIndex;
                while ((sepIndex = buffer.indexOf('\n\n')) !== -1) {
                    const rawEvent = buffer.slice(0, sepIndex);
                    buffer = buffer.slice(sepIndex + 2);
                    if (!rawEvent.trim()) continue;

                    const { eventName, data } = parseSseEvent(rawEvent);

                    if (eventName === 'token') {
                        if (!appended) {
                            appended = true;
                            setIsTyping(false);
                            setTypingLabel(null);
                            setMessages((prev) => [...prev, { id: assistantId, content: data.text, role: 'assistant' }]);
                        } else {
                            setMessages((prev) => prev.map((m) =>
                                m.id === assistantId ? { ...m, content: m.content + data.text } : m
                            ));
                        }
                    } else if (eventName === 'sources') {
                        setMessages((prev) => prev.map((m) =>
                            m.id === assistantId ? { ...m, sources: data.sources || null } : m
                        ));
                    } else if (eventName === 'status') {
                        if (data.stage === 'retrieve') retrieveEventCount += 1;
                        setTypingLabel(stageLabel(data.stage, retrieveEventCount));
                    } else if (eventName === 'error') {
                        showError(data.message || 'Произошла ошибка при получении ответа.');
                        if (!appended) {
                            appended = true;
                            setMessages((prev) => [...prev, {
                                id: assistantId,
                                content: 'Произошла ошибка при получении ответа.',
                                role: 'assistant',
                            }]);
                        }
                    }
                    // 'ping' — намеренно без действия, только держит соединение живым.
                }
            }
        } catch (e) {
            showError(e.message);
            if (!appended) {
                setMessages((prev) => [...prev, {
                    id: assistantId,
                    content: 'Произошла ошибка при получении ответа.',
                    role: 'assistant',
                }]);
            }
        } finally {
            setIsTyping(false);
            setIsStreaming(false);
            setTypingLabel(null);
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
        typingLabel,
        isStreaming,
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