// src/pages/ChatPage.jsx (Полная замена)

import React, { useState, useEffect, useRef } from 'react';
import MessageInput from '../components/MessageInput.jsx';
import Sidebar from '../components/Sidebar.jsx';
import Message from '../components/Message.jsx';

const initialMessages = [
    { id: 1, content: 'Привет! Я RAG Chat Pro. Задайте мне вопрос.', role: 'assistant' },
];

function ChatPage() {
    const [messages, setMessages] = useState(initialMessages);
    const [currentConversationId, setCurrentConversationId] = useState('temp-1');
    const messagesEndRef = useRef(null);

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
        // Классический двухколоночный контейнер
        <div className="app-layout">

            {/* 1. Левая колонка (История чатов) */}
            <Sidebar
                currentConversationId={currentConversationId}
                setCurrentConversationId={setCurrentConversationId}
            />

            {/* 2. Правая колонка (Сам чат) */}
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