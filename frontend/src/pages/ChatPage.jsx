// src/pages/ChatPage.jsx

import React, { useState, useEffect, useRef } from 'react';
import MessageInput from '../components/MessageInput.jsx';
import Sidebar from '../components/Sidebar.jsx';
import Message from '../components/Message.jsx';
import { BASE_API_URL, ENDPOINTS } from '../config/api'; // <-- Добавлено: импорт конфигурации API

function ChatPage({ accessToken }) { // <-- Принимаем токен как пропс
    const [messages, setMessages] = useState([
        { id: 1, content: 'Привет! Я RAG Chat Pro. Задайте мне вопрос.', role: 'assistant' },
    ]);
    const [currentConversationId, setCurrentConversationId] = useState(null);
    const [conversations, setConversations] = useState([]); // <-- Список чатов
    const messagesEndRef = useRef(null);

    // Загружаем список чатов пользователя
    const loadUserConversations = async () => {
        try {
            const response = await fetch(BASE_API_URL + ENDPOINTS.CONVERSATIONS, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${accessToken}`, // <-- Передаем токен в заголовке
                    'Content-Type': 'application/json',
                },
            });

            if (response.ok) {
                const data = await response.json();
                setConversations(data.conversations || []);
            } else {
                console.error('Failed to load conversations:', response.status);
            }
        } catch (error) {
            console.error('Error loading conversations:', error);
        }
    };

    // Загружаем историю конкретного чата
    const loadConversationHistory = async (conversationId) => {
        try {
            const response = await fetch(`${BASE_API_URL}/api/conversations/${conversationId}`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
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
                console.error('Failed to load conversation history:', response.status);
                // Если не удалось загрузить историю, очищаем сообщения
                setMessages([]);
            }
        } catch (error) {
            console.error('Error loading conversation history:', error);
            // Если произошла ошибка, очищаем сообщения
            setMessages([]);
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
            console.error('No conversation selected');
            return;
        }

        // Добавляем сообщение пользователя в UI сразу
        const userMessage = { id: Date.now(), content: text, role: 'user' };
        setMessages((prev) => [...prev, userMessage]);

        try {
            // Отправляем сообщение на бэкенд
            const response = await fetch(`${BASE_API_URL}/api/conversations/${currentConversationId}/messages`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
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
                console.error('Failed to send message:', response.status);
                // В случае ошибки показываем сообщение об ошибке
                const errorMessage = {
                    id: Date.now() + 1,
                    content: 'Ошибка при отправке сообщения',
                    role: 'assistant'
                };
                setMessages((prev) => [...prev, errorMessage]);
            }
        } catch (error) {
            console.error('Error sending message:', error);
            // В случае ошибки показываем сообщение об ошибке
            const errorMessage = {
                id: Date.now() + 1,
                content: 'Ошибка при отправке сообщения',
                role: 'assistant'
            };
            setMessages((prev) => [...prev, errorMessage]);
        }
    };

    return (
        <div className="app-layout">
            <Sidebar
                currentConversationId={currentConversationId}
                setCurrentConversationId={setCurrentConversationId}
                conversations={conversations}
                accessToken={accessToken}
                loadUserConversations={loadUserConversations} // <-- Передаем функцию загрузки чатов в сайдбар
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