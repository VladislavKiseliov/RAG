
// src/pages/ChatPage.jsx

import React, { useState, useEffect, useRef } from 'react';
import MessageInput from '../components/MessageInput.jsx';
import Sidebar from '../components/Sidebar.jsx';
import Message from '../components/Message.jsx';

function ChatPage({ accessToken }) { // <-- Принимаем токен как пропс
    const [messages, setMessages] = useState([
        { id: 1, content: 'Привет! Я RAG Chat Pro. Задайте мне вопрос.', role: 'assistant' },
    ]);
    const [currentConversationId, setCurrentConversationId] = useState(null);
    const [conversations, setConversations] = useState([]); // <-- Список чатов
    const messagesEndRef = useRef(null);

    // Загружаем список чатов пользователя
    useEffect(() => {
        if (accessToken) {
            loadUserConversations();
        }
    }, [accessToken]);

    // Функция для загрузки чатов пользователя
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

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSendMessage = (text) => {
        const userMessage = { id: Date.now(), content: text, role: 'user' };
        setMessages((prev) => [...prev, userMessage]);

        setTimeout(() => {
            const assistantResponse = {
                id: Date.now() + 1,
                content: `Вы сказали: "${text}". Жду ответа от FastAPI...`,
                role: 'assistant'
            };
            setMessages((prev) => [...prev, assistantResponse]);
        }, 1000);
    };

    return (
        <div className="app-layout">
            <Sidebar
                currentConversationId={currentConversationId}
                setCurrentConversationId={setCurrentConversationId}
                conversations={conversations}
                accessToken={accessToken} // <-- Передаем токен в сайдбар для API запросов
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