import React, { useState, useCallback } from 'react';
import { useClickOutside } from '../hooks/useClickOutside';
import { useApi, useShowError } from '../context/ApiContext';

function ChatList({ conversations, currentConversationId, onSelect, onRemoved, onRenamed }) {
    const api = useApi();
    const showError = useShowError();
    const [showMenu, setShowMenu] = useState(null);
    const [menuPosition, setMenuPosition] = useState({ x: 0, y: 0 });
    const [editingTitle, setEditingTitle] = useState(null);
    const [newTitle, setNewTitle] = useState('');
    const [confirmDeleteId, setConfirmDeleteId] = useState(null);
    const [processingChatId, setProcessingChatId] = useState(null);

    useClickOutside(!!showMenu, ['.chat-menu', '.chat-menu-button'], useCallback(() => {
        setShowMenu(null);
        setConfirmDeleteId(null);
    }, []));

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
            <div className="chat-list" id="chatList">
                {conversations && conversations.length > 0 ? (
                    conversations.map((chat) => (
                        <div
                            key={chat.chat_guid}
                            className={`chat-list-item ${currentConversationId === chat.chat_guid ? 'active' : ''}`}
                            onClick={() => onSelect(chat.chat_guid)}
                        >
                            {editingTitle === chat.chat_guid ? (
                                <div className="chat-title-edit">
                                    <input
                                        type="text"
                                        value={newTitle}
                                        onChange={(e) => setNewTitle(e.target.value)}
                                        onClick={(e) => e.stopPropagation()}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter') { e.stopPropagation(); saveTitle(chat.chat_guid); }
                                            if (e.key === 'Escape') { e.stopPropagation(); cancelEditing(); }
                                        }}
                                        autoFocus
                                    />
                                    <div className="edit-actions">
                                        <button
                                            className="save"
                                            onClick={(e) => { e.stopPropagation(); saveTitle(chat.chat_guid); }}
                                            disabled={processingChatId === chat.chat_guid}
                                        >
                                            {processingChatId === chat.chat_guid ? '...' : '✓'}
                                        </button>
                                        <button className="cancel" onClick={(e) => { e.stopPropagation(); cancelEditing(); }}>
                                            ✕
                                        </button>
                                    </div>
                                </div>
                            ) : (
                                <>
                                    <span className="ai-chip">
                                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none">
                                            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                        </svg>
                                    </span>
                                    <span className="chat-title">{chat.title}</span>
                                    <button
                                        className="chat-menu-button"
                                        onClick={(e) => toggleMenu(chat.chat_guid, e)}
                                        disabled={processingChatId === chat.chat_guid}
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
                                onClick={(e) => startEditingTitle(showMenu, conversations.find((c) => c.chat_guid === showMenu)?.title || '', e)}
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