import React, { useState, useCallback } from 'react';
import { formatUserName, formatUserInitial } from '../utils/formatUserName';
import { useClickOutside } from '../hooks/useClickOutside';

function MessengerChatList({ chats, activeChatGuid, onSelect, onDelete }) {
    const [showMenu, setShowMenu] = useState(null);
    const [menuPosition, setMenuPosition] = useState({ x: 0, y: 0 });
    const [confirmDeleteId, setConfirmDeleteId] = useState(null);
    const [processingId, setProcessingId] = useState(null);

    useClickOutside(!!showMenu, ['.chat-menu', '.chat-menu-button'], useCallback(() => {
        setShowMenu(null);
        setConfirmDeleteId(null);
    }, []));

    const toggleMenu = (chatGuid, event) => {
        event.stopPropagation();
        if (showMenu === chatGuid) {
            setShowMenu(null);
            setConfirmDeleteId(null);
        } else {
            const x = event.clientX;
            const y = event.clientY;
            const menuWidth = 150;
            const menuHeight = 60;
            const adjustedX = x + menuWidth > window.innerWidth ? window.innerWidth - menuWidth - 10 : x;
            const adjustedY = y + menuHeight > window.innerHeight ? y - menuHeight : y;
            setMenuPosition({ x: adjustedX, y: adjustedY });
            setShowMenu(chatGuid);
            setConfirmDeleteId(null);
        }
    };

    const handleDelete = async (chatGuid) => {
        setConfirmDeleteId(null);
        setShowMenu(null);
        setProcessingId(chatGuid);
        try {
            await onDelete?.(chatGuid);
        } finally {
            setProcessingId(null);
        }
    };

    if (!chats.length) {
        return <div className="chat-list-item empty">Нет чатов</div>;
    }

    return (
        <>
            <div className="chat-list">
                {chats.map((chat) => {
                    const guid = String(chat.chat_guid);
                    const name = formatUserName(chat, String(chat.friend_guid));
                    const initial = formatUserInitial(chat);

                    return (
                        <div
                            key={guid}
                            className={`chat-list-item messenger-item ${activeChatGuid === guid ? 'active' : ''}`}
                            onClick={() => onSelect(guid)}
                        >
                            <span className="user-avatar small">{initial}</span>
                            <div className="messenger-item-info">
                                <span className="chat-title">{name}</span>
                                {chat.last_message_content && (
                                    <span className="messenger-last-msg">{chat.last_message_content}</span>
                                )}
                            </div>
                            <button
                                className="chat-menu-button"
                                onClick={(e) => toggleMenu(guid, e)}
                                disabled={processingId === guid}
                                aria-label="Chat menu"
                            >
                                <span>&#8942;</span>
                            </button>
                        </div>
                    );
                })}
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
                                onClick={() => handleDelete(showMenu)}
                            >
                                Да, удалить
                            </button>
                            <button className="menu-item" onClick={() => setConfirmDeleteId(null)}>
                                Отмена
                            </button>
                        </>
                    ) : (
                        <button
                            className="menu-item delete"
                            onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(showMenu); }}
                        >
                            Удалить чат
                        </button>
                    )}
                </div>
            )}
        </>
    );
}

export default MessengerChatList;