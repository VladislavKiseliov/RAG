import React, { useState } from 'react';
import { ENDPOINTS } from '../config/api';
import ChatList from './ChatList.jsx';
import MessengerChatList from './MessengerChatList.jsx';
import UserPickerModal from './UserPickerModal.jsx';
import { useApi, useShowError } from '../context/ApiContext';

function SidebarSection({ title, onAdd, addTitle, children }) {
    const [open, setOpen] = useState(true);

    return (
        <div className="sidebar-section">
            <div className="sidebar-section-header" onClick={() => setOpen((v) => !v)}>
                <span className="chat-section-title">{title}</span>
                {onAdd && (
                    <span
                        className="sidebar-section-add"
                        title={addTitle}
                        onClick={(e) => { e.stopPropagation(); onAdd(); }}
                    >
                        +
                    </span>
                )}
            </div>
            {open && <div className="sidebar-section-content">{children}</div>}
        </div>
    );
}

function Sidebar({
    currentConversationId,
    setCurrentConversationId,
    conversations,
    loadUserConversations,
    onConversationRemoved,
    onConversationRenamed,
    messengerChats,
    activeChatGuid,
    onSelectMessengerChat,
    onCreateDirectChat,
    onDeleteMessengerChat,
    onToggleSidebar,
    isCollapsed,
    onOpenProjects,
}) {
    const api = useApi();
    const showError = useShowError();
    const [isCreatingAi, setIsCreatingAi] = useState(false);
    const [showUserPicker, setShowUserPicker] = useState(false);

    const handleNewAiChat = async () => {
        setIsCreatingAi(true);
        try {
            const data = await api.post(ENDPOINTS.CONVERSATIONS);
            setCurrentConversationId(data.conversation_id);
            loadUserConversations?.();
        } catch (e) {
            showError(e.message);
        } finally {
            setIsCreatingAi(false);
        }
    };

    const handleSelectUser = async (friendGuid) => {
        setShowUserPicker(false);
        await onCreateDirectChat?.(friendGuid);
    };

    if (isCollapsed) {
        return (
            <nav className="sidebar compact">
                <div className="sidebar-top">
                    <button className="icon-btn sidebar-toggle-btn" onClick={() => onToggleSidebar?.()} title="Развернуть">
                        <span className="toggle-sidebar-icon">▸</span>
                    </button>
                </div>
                <div className="compact-controls">
                    <button className="icon-btn" onClick={() => setShowUserPicker(true)} title="Новый чат">✉</button>
                    <button className="icon-btn" onClick={handleNewAiChat} title="Новый AI чат" disabled={isCreatingAi}>✦</button>
                </div>
                {showUserPicker && (
                    <UserPickerModal onSelect={handleSelectUser} onClose={() => setShowUserPicker(false)} />
                )}
            </nav>
        );
    }

    return (
        <nav className="sidebar">
            {/* Brand */}
            <div className="sidebar-brand">
                <div className="sidebar-brand-icon">И</div>
                <span className="sidebar-brand-name">Инжиниринг</span>
                <button className="icon-btn sidebar-toggle-btn" onClick={() => onToggleSidebar?.()} title="Свернуть">
                    ◂
                </button>
            </div>

            {/* Search */}
            <div className="sidebar-search">
                <span className="sidebar-search-icon">⌕</span>
                <input className="sidebar-search-input" placeholder="Поиск по докам и чатам" />
            </div>

            {/* Groups */}
            <div className="sidebar-groups">
                <SidebarSection title="Сообщения" onAdd={() => setShowUserPicker(true)} addTitle="Новый чат">
                    <MessengerChatList
                        chats={messengerChats ?? []}
                        activeChatGuid={activeChatGuid}
                        onSelect={onSelectMessengerChat}
                        onDelete={onDeleteMessengerChat}
                    />
                </SidebarSection>

                <SidebarSection title="Проекты" onAdd={onOpenProjects} addTitle="Новый проект">
                    <div className="project-create-btn" onClick={onOpenProjects}>
                        <span>＋</span> Создать первый проект
                    </div>
                </SidebarSection>

                <SidebarSection
                    title="AI-ассистент"
                    onAdd={handleNewAiChat}
                    addTitle={isCreatingAi ? 'Создание...' : 'Новый чат'}
                >
                    <ChatList
                        conversations={conversations}
                        currentConversationId={currentConversationId}
                        onSelect={setCurrentConversationId}
                        onRemoved={onConversationRemoved}
                        onRenamed={onConversationRenamed}
                    />
                </SidebarSection>
            </div>

            {showUserPicker && (
                <UserPickerModal onSelect={handleSelectUser} onClose={() => setShowUserPicker(false)} />
            )}
        </nav>
    );
}

export default Sidebar;
