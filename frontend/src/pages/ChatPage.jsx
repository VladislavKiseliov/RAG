// src/pages/ChatPage.jsx

import React, { useState, useEffect, useRef } from 'react';
import MessageInput from '../components/MessageInput.jsx';
import Sidebar from '../components/Sidebar.jsx';
import Message from '../components/Message.jsx';
import { BASE_API_URL, ENDPOINTS } from '../config/api'; // <-- Добавлено: импорт конфигурации API

function ChatPage({ accessToken, getAccessToken, onLogout }) { // <-- Принимаем токен как пропс
    const [messages, setMessages] = useState([
        { id: 1, content: 'Привет! Я RAG Chat Pro. Задайте мне вопрос.', role: 'assistant' },
    ]);
    const [currentConversationId, setCurrentConversationId] = useState(null);
    const [conversations, setConversations] = useState([]); // <-- Список чатов
    const [error, setError] = useState(null); // <-- НОВОЕ: Для отображения ошибок
    const [loading, setLoading] = useState(false); // <-- НОВОЕ: Для состояния загрузки
    const messagesEndRef = useRef(null);

    // Функция для отображения сообщения об ошибке
    const showError = (message) => {
        setError(message);
        setTimeout(() => setError(null), 5000); // Автоматически скрыть ошибку через 5 секунд
    };

    // Загружаем список чатов пользователя
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
                    'Authorization': `Bearer ${token}`, // <-- Передаем токен в заголовке
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

    // Загружаем историю конкретного чата
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
                // Преобразуем сообщения в формат, который ожидает компонент Message
                const formattedMessages = data.history.map(msg => ({
                    id: msg.id,
                    content: msg.content,
                    role: msg.role
                }));
                setMessages(formattedMessages);
            } else {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.detail || `Failed to load conversation history: ${response.status}`;
                console.error(errorMessage);
                showError(errorMessage);
                // Если не удалось загрузить историю, очищаем сообщения
                setMessages([]);
            }
        } catch (error) {
            console.error('Network error when loading conversation history:', error);
            showError('Network error when loading conversation history. Please check your connection.');
            // Если произошла ошибка, очищаем сообщения
            setMessages([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (accessToken) {
            loadUserConversations();
        }
    }, [accessToken]);

    // Эффект для загрузки истории чата при смене текущего чата
    useEffect(() => {
        if (currentConversationId) {
            loadConversationHistory(currentConversationId);
        } else {
            // Если нет выбранного чата, показываем приветственное сообщение
            setMessages([
                { id: 1, content: 'Привет! Я RAG Chat Pro. Задайте мне вопрос.', role: 'assistant' },
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
        if (!currentConversationId) {
            showError('Please select or create a conversation first');
            return;
        }

        // Добавляем сообщение пользователя в UI сразу
        const userMessage = { id: Date.now(), content: text, role: 'user' };
        setMessages((prev) => [...prev, userMessage]);

        try {
            // Отправляем сообщение на бэкенд
            const token = await getAccessToken();
            if (!token) {
                showError('Сессия истекла. Войдите снова.');
                return;
            }

            const response = await fetch(`${BASE_API_URL}/api/conversations/${currentConversationId}/messages`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ user_message: text }),
            });

            if (response.ok) {
                const data = await response.json();
                // Добавляем ответ ассистента
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
                // В случае ошибки показываем сообщение об ошибке
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
            // В случае ошибки показываем сообщение об ошибке
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
            {/* Отображение ошибок */}
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
                loadUserConversations={loadUserConversations} // <-- Передаем функцию загрузки чатов в сайдбар
                onLogout={onLogout}
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
