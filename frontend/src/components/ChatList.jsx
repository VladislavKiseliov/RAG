import React, { useState, useEffect } from 'react';

function ChatList({ api, conversations, currentConversationId, onSelect, onRemoved, onRenamed }) {
    const [showMenu, setShowMenu] = useState(null);
    const [menuPosition, setMenuPosition] = useState({ x: 0, y: 0 });
    const [editingTitle, setEditingTitle] = useState(null);
    const [newTitle, setNewTitle] = useState('');
    const [confirmDeleteId, setConfirmDeleteId] = useState(null);
    const [error, setError] = useState(null);
    const [processingChatId, setProcessingChatId] = useState(null);

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (showMenu && !event.target.closest('.chat-menu') && !event.target.closest('.chat-menu-button')) {
                setShowMenu(null);
                setConfirmDeleteId(null);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [showMenu]);

    const showError = (message) => {
        setError(message);
        setTimeout(() => setError(null), 5000);
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
            onRenamed?.(chatId, newTitle.trim());
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
            if (currentConversationId === chatId) onSelect(null);
            onRemoved?.(chatId);
        } catch (e) {
            showError(e.message);
        } finally {
            setProcessingChatId(null);
        }
    };

    return (
        <>
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
                            onClick={() => onSelect(chat.id)}
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
        </>
    );
}

export default ChatList;