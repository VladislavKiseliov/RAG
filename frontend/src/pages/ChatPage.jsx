// src/pages/ChatPage.jsx
import React, { useState, useEffect, useRef } from 'react';
import MessageInput from '../components/MessageInput.jsx';
import Sidebar from '../components/Sidebar.jsx';
import Message from '../components/Message.jsx';
import { BASE_API_URL, ENDPOINTS } from '../config/api';

function ChatPage({ accessToken, getAccessToken, onLogout, theme, onToggleTheme }) {
    const [messages, setMessages] = useState([
        { id: 1, content: 'Привет! Я ваш помощник по документации. Задайте вопрос.', role: 'assistant' },
    ]);
    const [isTyping, setIsTyping] = useState(false);
    const [currentConversationId, setCurrentConversationId] = useState(null);
    const [conversations, setConversations] = useState([]);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const messagesEndRef = useRef(null);
    const assistantGreeting = 'Привет! Я ваш помощник по документации. Задайте вопрос.';

    const showError = (message) => {
        setError(message);
        setTimeout(() => setError(null), 5000);
    };

    const loadUserConversations = async () => {
        setLoading(true);
        try {
            const token = await getAccessToken();
            if (!token) { showError('Сессия истекла. Войдите снова.'); return; }
            const response = await fetch(BASE_API_URL + ENDPOINTS.CONVERSATIONS, {
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            });
            if (response.ok) {
                const data = await response.json();
                setConversations(data.conversations || []);
            } else {
                const d = await response.json().catch(() => ({}));
                showError(d.detail || `Ошибка загрузки чатов: ${response.status}`);
            }
        } catch (e) {
            showError('Ошибка сети при загрузке чатов.');
        } finally {
            setLoading(false);
        }
    };

    const loadConversationHistory = async (conversationId) => {
        setLoading(true);
        try {
            const token = await getAccessToken();
            if (!token) { showError('Сессия истекла. Войдите снова.'); return; }
            const response = await fetch(`${BASE_API_URL}/api/chats/${conversationId}`, {
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            });
            if (response.ok) {
                const data = await response.json();
                const formatted = data.history.map(msg => ({
                    id: msg.id,
                    content: msg.content,
                    role: msg.role,
                    sources: msg.sources || null,
                }));
                setMessages(formatted.length === 0
                    ? [{ id: 1, content: assistantGreeting, role: 'assistant' }]
                    : formatted);
            } else {
                setMessages([{ id: 1, content: assistantGreeting, role: 'assistant' }]);
            }
        } catch (e) {
            setMessages([{ id: 1, content: assistantGreeting, role: 'assistant' }]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (accessToken) loadUserConversations();
    }, [accessToken]);

    useEffect(() => {
        if (currentConversationId) {
            loadConversationHistory(currentConversationId);
        } else {
            setMessages([{ id: 1, content: assistantGreeting, role: 'assistant' }]);
        }
    }, [currentConversationId]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isTyping]);

    const handleSendMessage = async (text) => {
        const ensureConversation = async () => {
            const token = await getAccessToken();
            if (!token) { showError('Сессия истекла.'); return null; }
            const res = await fetch(BASE_API_URL + ENDPOINTS.CONVERSATIONS, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            });
            if (!res.ok) { showError('Не удалось создать чат.'); return null; }
            const data = await res.json();
            setCurrentConversationId(data.conversation_id);
            loadUserConversations();
            setMessages([{ id: 1, content: assistantGreeting, role: 'assistant' }]);
            return data.conversation_id;
        };

        let conversationId = currentConversationId;
        if (!conversationId) {
            conversationId = await ensureConversation();
            if (!conversationId) return;
        }

        const userMessage = { id: Date.now(), content: text, role: 'user' };
        setMessages((prev) => [...prev, userMessage]);
        setIsTyping(true);

        try {
            const token = await getAccessToken();
            if (!token) { setIsTyping(false); showError('Сессия истекла.'); return; }

            const response = await fetch(BASE_API_URL + ENDPOINTS.MESSAGES(conversationId), {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_message: text }),
            });

            setIsTyping(false);

            if (response.ok) {
                const data = await response.json();
                // data.response — текст, data.sources — массив источников (если есть)
                const assistantMsg = {
                    id: Date.now() + 1,
                    content: data.response,
                    role: 'assistant',
                    sources: data.sources || null,
                };
                setMessages((prev) => [...prev, assistantMsg]);
            } else {
                const d = await response.json().catch(() => ({}));
                const errText = d.detail || `Ошибка: ${response.status}`;
                showError(errText);
                setMessages((prev) => [...prev, {
                    id: Date.now() + 1,
                    content: 'Произошла ошибка при получении ответа.',
                    role: 'assistant',
                }]);
            }
        } catch (e) {
            setIsTyping(false);
            showError('Ошибка сети.');
            setMessages((prev) => [...prev, {
                id: Date.now() + 1,
                content: 'Ошибка сети при отправке сообщения.',
                role: 'assistant',
            }]);
        }
    };

    return (
        <div className="app-layout">
            <Sidebar
                currentConversationId={currentConversationId}
                setCurrentConversationId={setCurrentConversationId}
                conversations={conversations}
                getAccessToken={getAccessToken}
                loadUserConversations={loadUserConversations}
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