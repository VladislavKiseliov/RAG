import React, { useState } from 'react';
import { ENDPOINTS } from '../config/api';
import ChatList from './ChatList.jsx';
import UserMenu from './UserMenu.jsx';

function Sidebar({
    api,
    currentConversationId,
    setCurrentConversationId,
    conversations,
    loadUserConversations,
    onConversationRemoved,
    onConversationRenamed,
    onLogout,
    onToggleSidebar,
    isCollapsed,
    theme,
    onToggleTheme,
}) {
    const [isCreating, setIsCreating] = useState(false);

    const handleNewChat = async () => {
        setIsCreating(true);
        try {
            const data = await api.post(ENDPOINTS.CONVERSATIONS);
            setCurrentConversationId(data.conversation_id);
            loadUserConversations?.();
        } catch {
            // error shown inline inside ChatList
        } finally {
            setIsCreating(false);
        }
    };

    if (isCollapsed) {
        return (
            <nav className="sidebar compact">
                <div className="sidebar-top">
                    <button className="icon-btn" onClick={() => onToggleSidebar?.()} aria-label="Развернуть панель" title="Скрыть/Показать панель">
                        <span className="toggle-sidebar-icon">🔖</span>
                    </button>
                </div>
                <div className="compact-controls">
                    <button className="icon-btn" onClick={handleNewChat} aria-label="Новый чат" title="Новый чат" disabled={isCreating}>
                        +
                    </button>
                </div>
                <UserMenu
                    api={api}
                    onLogout={onLogout}
                    theme={theme}
                    onToggleTheme={onToggleTheme}
                    footerClassName="compact-footer"
                />
            </nav>
        );
    }

    return (
        <nav className="sidebar">
            <div className="sidebar-top">
                <button className="icon-btn" onClick={() => onToggleSidebar?.()} aria-label="Свернуть панель" title="Скрыть/Показать панель">
                    <span className="toggle-sidebar-icon">🔖</span>
                </button>
            </div>
            <div className="sidebar-header">
                <button className="new-chat-btn" id="newChatBtn" onClick={handleNewChat} disabled={isCreating}>
                    <span className="new-chat-icon">+</span>
                    {isCreating ? 'Создание...' : 'Новый чат'}
                </button>
                <div className="chat-section-title">Чаты</div>
            </div>

            <ChatList
                api={api}
                conversations={conversations}
                currentConversationId={currentConversationId}
                onSelect={setCurrentConversationId}
                onRemoved={onConversationRemoved}
                onRenamed={onConversationRenamed}
            />

            <UserMenu
                api={api}
                onLogout={onLogout}
                theme={theme}
                onToggleTheme={onToggleTheme}
            />
        </nav>
    );
}

export default Sidebar;