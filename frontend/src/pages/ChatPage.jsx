import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import MessageInput from '../components/MessageInput.jsx';
import Sidebar from '../components/Sidebar.jsx';
import Message from '../components/Message.jsx';
import { createApiClient } from '../api/client';
import { ENDPOINTS } from '../config/api';

const GREETING = { id: 'greeting', content: 'Привет! Я ваш помощник по документации. Задайте вопрос.', role: 'assistant' };

function ChatPage({ accessToken, getAccessToken, onLogout, theme, onToggleTheme }) {
    const [messages, setMessages] = useState([GREETING]);
    const [isTyping, setIsTyping] = useState(false);
    const [currentConversationId, setCurrentConversationId] = useState(null);
    const [conversations, setConversations] = useState([]);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const messagesEndRef = useRef(null);
    const historyAbortRef = useRef(null);

    const api = useMemo(() => createApiClient(getAccessToken), [getAccessToken]);

    const showError = useCallback((message) => {
        setError(message);
        setTimeout(() => setError(null), 5000);
    }, []);

    const loadUserConversations = useCallback(async () => {
        setLoading(true);
        try {
            const data = await api.get(ENDPOINTS.CONVERSATIONS);
            setConversations(data.conversations || []);
        } catch (e) {
            showError(e.message);
        } finally {
            setLoading(false);
        }
    }, [api, showError]);

    const loadConversationHistory = useCallback(async (conversationId) => {
        historyAbortRef.current?.abort();
        const controller = new AbortController();
        historyAbortRef.current = controller;
        setLoading(true);
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
        } finally {
            if (!controller.signal.aborted) setLoading(false);
        }
    }, [api]);

    useEffect(() => {
        if (accessToken) loadUserConversations();
    }, [accessToken]);

    useEffect(() => {
        if (currentConversationId) {
            loadConversationHistory(currentConversationId);
        } else {
            historyAbortRef.current?.abort();
            setMessages([GREETING]);
        }
        return () => historyAbortRef.current?.abort();
    }, [currentConversationId]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isTyping]);

    const handleSendMessage = useCallback(async (text) => {
        let conversationId = currentConversationId;
        if (!conversationId) {
            try {
                const data = await api.post(ENDPOINTS.CONVERSATIONS);
                conversationId = data.conversation_id;
                setCurrentConversationId(conversationId);
                setMessages([GREETING]);
                loadUserConversations();
            } catch (e) {
                showError(e.message);
                return;
            }
        }

        setMessages((prev) => [...prev, { id: crypto.randomUUID(), content: text, role: 'user' }]);
        setIsTyping(true);

        try {
            const data = await api.post(ENDPOINTS.MESSAGES(conversationId), { user_message: text });
            setMessages((prev) => [...prev, {
                id: crypto.randomUUID(),
                content: data.response,
                role: 'assistant',
                sources: data.sources || null,
            }]);
        } catch (e) {
            showError(e.message);
            setMessages((prev) => [...prev, {
                id: crypto.randomUUID(),
                content: 'Произошла ошибка при получении ответа.',
                role: 'assistant',
            }]);
        } finally {
            setIsTyping(false);
        }
    }, [api, currentConversationId, loadUserConversations, showError]);

    const removeConversation = useCallback(
        (id) => setConversations((prev) => prev.filter((c) => c.id !== id)),
        []
    );

    const renameConversation = useCallback(
        (id, title) => setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, title } : c))),
        []
    );

    return (
        <div className="app-layout">
            <Sidebar
                api={api}
                currentConversationId={currentConversationId}
                setCurrentConversationId={setCurrentConversationId}
                conversations={conversations}
                loadUserConversations={loadUserConversations}
                onConversationRemoved={removeConversation}
                onConversationRenamed={renameConversation}
                onLogout={onLogout}
                theme={theme}
                onToggleTheme={onToggleTheme}
                onToggleSidebar={() => setSidebarCollapsed((v) => !v)}
                isCollapsed={sidebarCollapsed}
            />
            <main className="main-chat">
                {error && (
                    <div className="error-toast">
                        <span>⚠ {error}</span>
                    </div>
                )}
                <div className="chat-container">
                    <div className="chat-history" id="chatHistory">
                        {messages.map((msg) => (
                            <Message
                                key={msg.id}
                                content={msg.content}
                                role={msg.role}
                                sources={msg.sources}
                            />
                        ))}
                        {isTyping && <Message isTyping />}
                        <div ref={messagesEndRef} />
                    </div>
                    <MessageInput onSendMessage={handleSendMessage} disabled={isTyping} />
                </div>
            </main>
        </div>
    );
}

export default ChatPage;