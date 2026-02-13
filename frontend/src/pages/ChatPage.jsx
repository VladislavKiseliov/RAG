// src/pages/ChatPage.jsx

import React, { useState, useEffect, useRef } from 'react';
import MessageInput from '../components/MessageInput.jsx';
import Sidebar from '../components/Sidebar.jsx';
import Message from '../components/Message.jsx';
import { BASE_API_URL, ENDPOINTS } from '../config/api'; // <-- Р”РѕР±Р°РІР»РµРЅРѕ: РёРјРїРѕСЂС‚ РєРѕРЅС„РёРіСѓСЂР°С†РёРё API

function ChatPage({ accessToken, getAccessToken, onLogout, theme, onToggleTheme }) { // <-- РџСЂРёРЅРёРјР°РµРј С‚РѕРєРµРЅ РєР°Рє РїСЂРѕРїСЃ
    const [messages, setMessages] = useState([
        { id: 1, content: 'Я ваш помощник, чем могу помочь?', role: 'assistant' },
    ]);
    const [currentConversationId, setCurrentConversationId] = useState(null);
    const [conversations, setConversations] = useState([]); // <-- РЎРїРёСЃРѕРє С‡Р°С‚РѕРІ
    const [error, setError] = useState(null); // <-- РќРћР’РћР•: Р”Р»СЏ РѕС‚РѕР±СЂР°Р¶РµРЅРёСЏ РѕС€РёР±РѕРє
    const [loading, setLoading] = useState(false); // <-- РќРћР’РћР•: Р”Р»СЏ СЃРѕСЃС‚РѕСЏРЅРёСЏ Р·Р°РіСЂСѓР·РєРё
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const messagesEndRef = useRef(null);
    const assistantGreeting = 'Я ваш помощник, чем могу помочь?';

    // Р¤СѓРЅРєС†РёСЏ РґР»СЏ РѕС‚РѕР±СЂР°Р¶РµРЅРёСЏ СЃРѕРѕР±С‰РµРЅРёСЏ РѕР± РѕС€РёР±РєРµ
    const showError = (message) => {
        setError(message);
        setTimeout(() => setError(null), 5000); // РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРё СЃРєСЂС‹С‚СЊ РѕС€РёР±РєСѓ С‡РµСЂРµР· 5 СЃРµРєСѓРЅРґ
    };

    // Р—Р°РіСЂСѓР¶Р°РµРј СЃРїРёСЃРѕРє С‡Р°С‚РѕРІ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
    const loadUserConversations = async () => {
        setLoading(true);
        try {
            const token = await getAccessToken();
            if (!token) {
                showError('Сессия истекла. Войдите снова.');
                setLoading(false);
                return;
            }
            const response = await fetch(BASE_API_URL + ENDPOINTS.CONVERSATIONS, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`, // <-- РџРµСЂРµРґР°РµРј С‚РѕРєРµРЅ РІ Р·Р°РіРѕР»РѕРІРєРµ
                    'Content-Type': 'application/json',
                },
            });

            if (response.ok) {
                const data = await response.json();
                setConversations(data.conversations || []);
            } else {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.detail || `Failed to load conversations: ${response.status}`;
                console.error(errorMessage);
                showError(errorMessage);
            }
        } catch (error) {
            console.error('Network error when loading conversations:', error);
            showError('Network error when loading conversations. Please check your connection.');
        } finally {
            setLoading(false);
        }
    };

    // Р—Р°РіСЂСѓР¶Р°РµРј РёСЃС‚РѕСЂРёСЋ РєРѕРЅРєСЂРµС‚РЅРѕРіРѕ С‡Р°С‚Р°
    const loadConversationHistory = async (conversationId) => {
        setLoading(true);
        try {
            const token = await getAccessToken();
            if (!token) {
                showError('Сессия истекла. Войдите снова.');
                setLoading(false);
                return;
            }
            const response = await fetch(`${BASE_API_URL}/api/conversations/${conversationId}`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
            });

            if (response.ok) {
                const data = await response.json();
                // РџСЂРµРѕР±СЂР°Р·СѓРµРј СЃРѕРѕР±С‰РµРЅРёСЏ РІ С„РѕСЂРјР°С‚, РєРѕС‚РѕСЂС‹Р№ РѕР¶РёРґР°РµС‚ РєРѕРјРїРѕРЅРµРЅС‚ Message
                const formattedMessages = data.history.map(msg => ({
                    id: msg.id,
                    content: msg.content,
                    role: msg.role
                }));
                if (formattedMessages.length === 0) {
                    setMessages([{ id: 1, content: assistantGreeting, role: 'assistant' }]);
                } else {
                    setMessages(formattedMessages);
                }
            } else {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.detail || `Failed to load conversation history: ${response.status}`;
                console.error(errorMessage);
                showError(errorMessage);
                // Р•СЃР»Рё РЅРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ РёСЃС‚РѕСЂРёСЋ, РѕС‡РёС‰Р°РµРј СЃРѕРѕР±С‰РµРЅРёСЏ
                setMessages([{ id: 1, content: assistantGreeting, role: 'assistant' }]);
            }
        } catch (error) {
            console.error('Network error when loading conversation history:', error);
            showError('Network error when loading conversation history. Please check your connection.');
            // Р•СЃР»Рё РїСЂРѕРёР·РѕС€Р»Р° РѕС€РёР±РєР°, РѕС‡РёС‰Р°РµРј СЃРѕРѕР±С‰РµРЅРёСЏ
            setMessages([{ id: 1, content: assistantGreeting, role: 'assistant' }]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (accessToken) {
            loadUserConversations();
        }
    }, [accessToken]);

    // Р­С„С„РµРєС‚ РґР»СЏ Р·Р°РіСЂСѓР·РєРё РёСЃС‚РѕСЂРёРё С‡Р°С‚Р° РїСЂРё СЃРјРµРЅРµ С‚РµРєСѓС‰РµРіРѕ С‡Р°С‚Р°
    useEffect(() => {
        if (currentConversationId) {
            loadConversationHistory(currentConversationId);
        } else {
            // Р•СЃР»Рё РЅРµС‚ РІС‹Р±СЂР°РЅРЅРѕРіРѕ С‡Р°С‚Р°, РїРѕРєР°Р·С‹РІР°РµРј РїСЂРёРІРµС‚СЃС‚РІРµРЅРЅРѕРµ СЃРѕРѕР±С‰РµРЅРёРµ
            setMessages([
                { id: 1, content: assistantGreeting, role: 'assistant' },
            ]);
        }
    }, [currentConversationId]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSendMessage = async (text) => {
        // Р•СЃР»Рё С‡Р°С‚ РµС‰Рµ РЅРµ СЃРѕР·РґР°РЅ вЂ” СЃРѕР·РґР°РµРј РµРіРѕ РїСЂСЏРјРѕ РїСЂРё РїРµСЂРІРѕРј СЃРѕРѕР±С‰РµРЅРёРё
        const ensureConversation = async () => {
            const token = await getAccessToken();
            if (!token) {
                showError('Сессия истекла. Войдите снова.');
                return null;
            }
            const response = await fetch(BASE_API_URL + ENDPOINTS.CONVERSATIONS, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.detail || `Failed to create new chat: ${response.status}`;
                console.error(errorMessage);
                showError(errorMessage);
                return null;
            }

            const data = await response.json();
            setCurrentConversationId(data.conversation_id);
            if (loadUserConversations) {
                loadUserConversations();
            }
            // РЈР±РёСЂР°РµРј РїСЂРёРІРµС‚СЃС‚РІРёРµ, С‡С‚РѕР±С‹ РёСЃС‚РѕСЂРёСЏ Р±С‹Р»Р° С‡РёСЃС‚РѕР№
            setMessages([{ id: 1, content: assistantGreeting, role: 'assistant' }]);
            return data.conversation_id;
        };

        let conversationId = currentConversationId;
        if (!conversationId) {
            conversationId = await ensureConversation();
            if (!conversationId) {
                return;
            }
        }

        // Р”РѕР±Р°РІР»СЏРµРј СЃРѕРѕР±С‰РµРЅРёРµ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РІ UI СЃСЂР°Р·Сѓ
        const userMessage = { id: Date.now(), content: text, role: 'user' };
        setMessages((prev) => [...prev, userMessage]);

        try {
            // РћС‚РїСЂР°РІР»СЏРµРј СЃРѕРѕР±С‰РµРЅРёРµ РЅР° Р±СЌРєРµРЅРґ
            const token = await getAccessToken();
            if (!token) {
                showError('Сессия истекла. Войдите снова.');
                return;
            }

            const response = await fetch(`${BASE_API_URL}/api/conversations/${conversationId}/messages`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ user_message: text }),
            });

            if (response.ok) {
                const data = await response.json();
                // Р”РѕР±Р°РІР»СЏРµРј РѕС‚РІРµС‚ Р°СЃСЃРёСЃС‚РµРЅС‚Р°
                const assistantResponse = {
                    id: Date.now() + 1,
                    content: data.response,
                    role: 'assistant'
                };
                setMessages((prev) => [...prev, assistantResponse]);
            } else {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.detail || `Failed to send message: ${response.status}`;
                console.error(errorMessage);
                showError(errorMessage);
                // Р’ СЃР»СѓС‡Р°Рµ РѕС€РёР±РєРё РїРѕРєР°Р·С‹РІР°РµРј СЃРѕРѕР±С‰РµРЅРёРµ РѕР± РѕС€РёР±РєРµ
                const errorMessageResponse = {
                    id: Date.now() + 1,
                    content: 'Ошибка при отправке сообщения: ' + errorMessage,
                    role: 'assistant'
                };
                setMessages((prev) => [...prev, errorMessageResponse]);
            }
        } catch (error) {
            console.error('Network error when sending message:', error);
            showError('Network error when sending message. Please check your connection.');
            // Р’ СЃР»СѓС‡Р°Рµ РѕС€РёР±РєРё РїРѕРєР°Р·С‹РІР°РµРј СЃРѕРѕР±С‰РµРЅРёРµ РѕР± РѕС€РёР±РєРµ
            const errorMessage = {
                id: Date.now() + 1,
                content: 'Ошибка сети при отправке сообщения',
                role: 'assistant'
            };
            setMessages((prev) => [...prev, errorMessage]);
        }
    };

    return (
        <div className="app-layout">
            {/* РћС‚РѕР±СЂР°Р¶РµРЅРёРµ РѕС€РёР±РѕРє */}
            {error && (
                <div style={{ 
                    color: 'red', 
                    padding: '10px', 
                    margin: '10px', 
                    border: '1px solid red', 
                    borderRadius: '4px',
                    backgroundColor: '#ffe6e6'
                }}>
                    {error}
                </div>
            )}
            
            <Sidebar
                currentConversationId={currentConversationId}
                setCurrentConversationId={setCurrentConversationId}
                conversations={conversations}
                getAccessToken={getAccessToken}
                loadUserConversations={loadUserConversations} // <-- РџРµСЂРµРґР°РµРј С„СѓРЅРєС†РёСЋ Р·Р°РіСЂСѓР·РєРё С‡Р°С‚РѕРІ РІ СЃР°Р№РґР±Р°СЂ
                onLogout={onLogout}
                theme={theme}
                onToggleTheme={onToggleTheme}
                onToggleSidebar={() => setSidebarCollapsed((v) => !v)}
                isCollapsed={sidebarCollapsed}
            />
            <main className="main-chat">
                <div className="chat-container">
                    <div className="chat-history" id="chatHistory">
                        {messages.map((msg) => (
                            <Message key={msg.id} content={msg.content} role={msg.role} />
                        ))}
                        <div ref={messagesEndRef} />
                    </div>
                    <MessageInput onSendMessage={handleSendMessage} />
                </div>
            </main>
        </div>
    );
}

export default ChatPage;





