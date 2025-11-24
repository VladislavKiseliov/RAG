// src/components/Sidebar.js

import React from 'react';
import { BASE_API_URL, ENDPOINTS } from '../config/api';

function Sidebar({ currentConversationId, setCurrentConversationId, accessToken }) { // <-- Добавлено: принимаем accessToken как пропс
    // Функция для создания нового чата
    const handleNewChat = async () => {
        try {
            const response = await fetch(BASE_API_URL + ENDPOINTS.CONVERSATIONS, { // <-- Исправлено: используем ENDPOINTS.CONVERSATIONS
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${accessToken}`, // accessToken - токен, полученный при вход
                    'Content-Type': 'application/json',
                },
            });

            if (response.ok) {
                const data = await response.json();
                // Устанавливаем новый чат как текущий
                setCurrentConversationId(data.conversation_id);
            } else {
                console.error('Failed to create new chat:', response.status);
            }
        } catch (error) {
            console.error('Error creating new chat:', error);
        }
    };

    return (
        <nav className="sidebar">
            <div className="sidebar-header">
                <button className="new-chat-btn" id="newChatBtn" onClick={handleNewChat}>
                    + Новый чат
                </button>
            </div>
            <div className="chat-list" id="chatList">
                {/* Здесь будет список компонентов ChatListItem */}
                <div
                    className={`chat-list-item ${currentConversationId === 'temp-1' ? 'active' : ''}`}
                    onClick={() => setCurrentConversationId('temp-1')}
                >
                    Текущий чат
                </div>
            </div>
        </nav>
    );
}

export default Sidebar;
