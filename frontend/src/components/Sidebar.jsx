import React, { useState, useCallback } from 'react';
import { ENDPOINTS } from '../config/api';
import ChatList from './ChatList.jsx';
import MessengerChatList from './MessengerChatList.jsx';
import UserPickerModal from './UserPickerModal.jsx';
import ProfileModal from './ProfileModal.jsx';
import UserMenu from './UserMenu.jsx';
import { useApi, useShowError } from '../context/ApiContext';
import { useClickOutside } from '../hooks/useClickOutside';

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
    onLogout,
    onToggleSidebar,
    isCollapsed,
    theme,
    onToggleTheme,
    onOpenProjects,
    currentUser,
}) {
    const api = useApi();
    const showError = useShowError();
    const [isCreatingAi, setIsCreatingAi] = useState(false);
    const [showUserPicker, setShowUserPicker] = useState(false);
    const [showProfile, setShowProfile] = useState(false);
    const [profileOpen, setProfileOpen] = useState(false);
    const userInfo = currentUser ?? { initials: '..', name: '', role: '', login: '' };

    useClickOutside(
        profileOpen,
        ['.sidebar-user-row', '.profile-dropdown'],
        useCallback(() => setProfileOpen(false), [])
    );

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
                <UserMenu initials={userInfo.initials} onLogout={onLogout} theme={theme} onToggleTheme={onToggleTheme} footerClassName="compact-footer" />
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

            {/* User row */}
            <div className="sidebar-user-row">
                <div className="sidebar-user-row-inner" onClick={() => setProfileOpen((v) => !v)}>
                    <div className="sidebar-user-avatar-wrap">{userInfo.initials}</div>
                    <div className="sidebar-user-info">
                        <div className="sidebar-user-name">{userInfo.name || userInfo.login}</div>
                        <div className="sidebar-user-role">{userInfo.role}</div>
                    </div>
                    <span className={`sidebar-user-caret${profileOpen ? ' open' : ''}`}>▾</span>
                </div>

                {profileOpen && (
                    <div className="profile-dropdown" onClick={(e) => e.stopPropagation()}>
                        <div className="profile-dropdown-header">
                            <div className="profile-dropdown-avatar">{userInfo.initials}</div>
                            <div>
                                <div className="profile-dropdown-name">{userInfo.name || userInfo.login}</div>
                                <div className="profile-dropdown-meta">{userInfo.login}{userInfo.role ? ` · ${userInfo.role}` : ''}</div>
                            </div>
                        </div>
                        <div className="profile-dropdown-items">
                            <button
                                className="profile-dropdown-item"
                                onClick={() => { setProfileOpen(false); setShowProfile(true); }}
                            >
                                <span className="item-left"><span className="item-icon">◴</span> Профиль и данные</span>
                            </button>
                            <button className="profile-dropdown-item">
                                <span className="item-left"><span className="item-icon">⚙</span> Настройки</span>
                            </button>
                            <div className="profile-dropdown-item" style={{ cursor: 'default' }}>
                                <span className="item-left"><span className="item-icon">◐</span> Тема</span>
                                <div className="theme-pills">
                                    <button
                                        className={`theme-pill${theme === 'dark' ? ' active' : ''}`}
                                        onClick={() => theme !== 'dark' && onToggleTheme?.()}
                                    >
                                        Тёмная
                                    </button>
                                    <button
                                        className={`theme-pill${theme === 'light' ? ' active' : ''}`}
                                        onClick={() => theme !== 'light' && onToggleTheme?.()}
                                    >
                                        Светлая
                                    </button>
                                </div>
                            </div>
                            <div className="profile-dropdown-divider" />
                            <button
                                className="profile-dropdown-item danger"
                                onClick={() => { setProfileOpen(false); onLogout?.(true); }}
                            >
                                <span className="item-left"><span>⎋</span> Выйти</span>
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {showUserPicker && (
                <UserPickerModal onSelect={handleSelectUser} onClose={() => setShowUserPicker(false)} />
            )}
            {showProfile && (
                <ProfileModal onClose={() => setShowProfile(false)} />
            )}
        </nav>
    );
}

export default Sidebar;
