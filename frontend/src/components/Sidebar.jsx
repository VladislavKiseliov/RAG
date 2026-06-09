import React, { useState, useEffect } from 'react';
import { ENDPOINTS } from '../config/api';
import ProfileModal from './ProfileModal.jsx';

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
    const [showMenu, setShowMenu] = useState(null);
    const [menuPosition, setMenuPosition] = useState({ x: 0, y: 0 });
    const [editingTitle, setEditingTitle] = useState(null);
    const [newTitle, setNewTitle] = useState('');
    const [confirmDeleteId, setConfirmDeleteId] = useState(null);
    const [error, setError] = useState(null);
    const [isCreating, setIsCreating] = useState(false);
    const [processingChatId, setProcessingChatId] = useState(null);
    const [showUserMenu, setShowUserMenu] = useState(false);
    const [showProfile, setShowProfile] = useState(false);

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (showMenu && !event.target.closest('.chat-menu') && !event.target.closest('.chat-menu-button')) {
                setShowMenu(null);
                setConfirmDeleteId(null);
            }
            if (showUserMenu && !event.target.closest('.user-menu') && !event.target.closest('.user-menu-button')) {
                setShowUserMenu(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [showMenu, showUserMenu]);

    const showError = (message) => {
        setError(message);
        setTimeout(() => setError(null), 5000);
    };

    const handleNewChat = async () => {
        setIsCreating(true);
        try {
            const data = await api.post(ENDPOINTS.CONVERSATIONS);
            setCurrentConversationId(data.conversation_id);
            loadUserConversations?.();
        } catch (e) {
            showError(e.message);
        } finally {
            setIsCreating(false);
        }
    };

    const toggleMenu = (chatId, event) => {
        event.stopPropagation();
        if (showMenu === chatId) {
            setShowMenu(null);
            setConfirmDeleteId(null);
        } else {
            const x = event.clientX;
            const y = event.clientY;
            const menuWidth = 150;
            const menuHeight = 80;
            const adjustedX = x + menuWidth > window.innerWidth ? window.innerWidth - menuWidth - 10 : x;
            const adjustedY = y + menuHeight > window.innerHeight ? y - menuHeight : y;
            setMenuPosition({ x: adjustedX, y: adjustedY });
            setShowMenu(chatId);
            setConfirmDeleteId(null);
        }
    };

    const startEditingTitle = (chatId, currentTitle, event) => {
        event.stopPropagation();
        setEditingTitle(chatId);
        setNewTitle(currentTitle);
        setShowMenu(null);
    };

    const saveTitle = async (chatId) => {
        if (!newTitle.trim()) { setEditingTitle(null); return; }
        setProcessingChatId(chatId);
        try {
            await api.patch(`/api/chats/${chatId}/rename`, { title: newTitle.trim() });
            onConversationRenamed?.(chatId, newTitle.trim());
            setEditingTitle(null);
        } catch (e) {
            showError(e.message);
        } finally {
            setProcessingChatId(null);
        }
    };

    const cancelEditing = () => {
        setEditingTitle(null);
        setNewTitle('');
    };

    const deleteChat = async (chatId) => {
        setConfirmDeleteId(null);
        setShowMenu(null);
        setProcessingChatId(chatId);
        try {
            await api.delete(`/api/chats/${chatId}`);
            if (currentConversationId === chatId) setCurrentConversationId(null);
            onConversationRemoved?.(chatId);
        } catch (e) {
            showError(e.message);
        } finally {
            setProcessingChatId(null);
        }
    };

    const userMenuContent = (
        <div className="user-menu" onClick={(e) => e.stopPropagation()}>
            <button className="menu-item" onClick={() => { setShowUserMenu(false); setShowProfile(true); }}>
                Профиль
            </button>
            <button className="menu-item" onClick={() => alert('Справка: это базовая база знаний.')}>
                Справка
            </button>
            <button className="menu-item" onClick={() => onToggleTheme?.()}>
                Тема: {theme === 'light' ? 'Светлая' : 'Темная'}
            </button>
            <button className="menu-item" onClick={() => onLogout?.(true)}>
                Выйти
            </button>
            <button className="menu-item" disabled>
                Настройки
            </button>
        </div>
    );

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
                <div className="compact-footer">
                    <button className="user-menu-button" onClick={() => setShowUserMenu((prev) => !prev)} aria-label="User menu">
                        <span className="user-menu-avatar">RG</span>
                    </button>
                    {showUserMenu && userMenuContent}
                </div>
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

            {error && (
                <div className="error-message" style={{
                    color: 'red', padding: '10px', margin: '10px',
                    border: '1px solid red', borderRadius: '4px', backgroundColor: '#ffe6e6',
                }}>
                    {error}
                </div>
            )}

            <div className="chat-list" id="chatList">
                {conversations && conversations.length > 0 ? (
                    conversations.map((chat) => (
                        <div
                            key={chat.id}
                            className={`chat-list-item ${currentConversationId === chat.id ? 'active' : ''}`}
                            onClick={() => setCurrentConversationId(chat.id)}
                        >
                            {editingTitle === chat.id ? (
                                <div className="chat-title-edit">
                                    <input
                                        type="text"
                                        value={newTitle}
                                        onChange={(e) => setNewTitle(e.target.value)}
                                        onClick={(e) => e.stopPropagation()}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter') { e.stopPropagation(); saveTitle(chat.id); }
                                            if (e.key === 'Escape') { e.stopPropagation(); cancelEditing(); }
                                        }}
                                        autoFocus
                                    />
                                    <div className="edit-actions">
                                        <button
                                            className="save"
                                            onClick={(e) => { e.stopPropagation(); saveTitle(chat.id); }}
                                            disabled={processingChatId === chat.id}
                                        >
                                            {processingChatId === chat.id ? '...' : '✓'}
                                        </button>
                                        <button className="cancel" onClick={(e) => { e.stopPropagation(); cancelEditing(); }}>
                                            ✕
                                        </button>
                                    </div>
                                </div>
                            ) : (
                                <>
                                    <span className="chat-title">{chat.title}</span>
                                    <button
                                        className="chat-menu-button"
                                        onClick={(e) => toggleMenu(chat.id, e)}
                                        disabled={processingChatId === chat.id}
                                        aria-label="Chat menu"
                                    >
                                        <span>&#8942;</span>
                                    </button>
                                </>
                            )}
                        </div>
                    ))
                ) : (
                    <div className="chat-list-item empty">Нет чатов</div>
                )}
            </div>

            {showMenu && (
                <div
                    className="chat-menu"
                    onClick={(e) => e.stopPropagation()}
                    style={{
                        position: 'fixed',
                        top: `${menuPosition.y}px`,
                        left: `${menuPosition.x}px`,
                        transform: 'translate(-100%, 0)',
                        zIndex: 9999,
                    }}
                >
                    {confirmDeleteId === showMenu ? (
                        <>
                            <span className="menu-item-text">Удалить чат?</span>
                            <button
                                className="menu-item delete"
                                onClick={(e) => { e.stopPropagation(); deleteChat(showMenu); }}
                            >
                                Да, удалить
                            </button>
                            <button className="menu-item" onClick={() => setConfirmDeleteId(null)}>
                                Отмена
                            </button>
                        </>
                    ) : (
                        <>
                            <button
                                className="menu-item"
                                onClick={(e) => startEditingTitle(showMenu, conversations.find((c) => c.id === showMenu)?.title || '', e)}
                            >
                                Изменить название
                            </button>
                            <button
                                className="menu-item delete"
                                onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(showMenu); }}
                            >
                                Удалить чат
                            </button>
                        </>
                    )}
                </div>
            )}

            {showProfile && (
                <ProfileModal
                    api={api}
                    onClose={() => setShowProfile(false)}
                />
            )}

            <div className="sidebar-footer">
                <button
                    className="user-menu-button"
                    onClick={() => setShowUserMenu((prev) => !prev)}
                    aria-label="User menu"
                >
                    <span className="user-menu-avatar">RG</span>
                </button>
                {showUserMenu && userMenuContent}
            </div>
        </nav>
    );
}

export default Sidebar;