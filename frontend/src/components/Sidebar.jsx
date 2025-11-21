// src/components/Sidebar.js

import React from 'react';

function Sidebar({ currentConversationId, setCurrentConversationId }) {
    // В реальном приложении здесь будет загрузка списка чатов с FastAPI

    return (
        <nav className="sidebar">
            <div className="sidebar-header">
                <button className="new-chat-btn" id="newChatBtn">
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