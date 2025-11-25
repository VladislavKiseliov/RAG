// src/components/Sidebar.js

import React, { useState, useEffect, useRef } from 'react';
import { BASE_API_URL, ENDPOINTS } from '../config/api';

function Sidebar({ currentConversationId, setCurrentConversationId, conversations, accessToken, loadUserConversations }) {
    // Состояния для управления меню действий над чатом
    const [showMenu, setShowMenu] = useState(null); // null или ID чата, для которого открыто меню
    const [menuPosition, setMenuPosition] = useState({ x: 0, y: 0 }); // Позиция меню
    const [editingTitle, setEditingTitle] = useState(null); // null или ID чата, который редактируется
    const [newTitle, setNewTitle] = useState(''); // Новое название чата при редактировании
    const menuButtonRef = useRef({}); // Рефы для кнопок меню

    // Функция для закрытия меню при клике вне его области
    useEffect(() => {
        const handleClickOutside = (event) => {
            // Проверяем, был ли клик вне меню
            if (showMenu && !event.target.closest('.chat-menu') && !event.target.closest('.chat-menu-button')) {
                setShowMenu(null);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [showMenu]);

    // Функция для создания нового чата
    const handleNewChat = async () => {
        try {
            const response = await fetch(BASE_API_URL + ENDPOINTS.CONVERSATIONS, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Content-Type': 'application/json',
                },
            });

            if (response.ok) {
                const data = await response.json();
                // Устанавливаем новый чат как текущий
                setCurrentConversationId(data.conversation_id);
                // Обновляем список чатов после создания нового
                if (loadUserConversations) {
                    loadUserConversations();
                }
            } else {
                console.error('Failed to create new chat:', response.status);
            }
        } catch (error) {
            console.error('Error creating new chat:', error);
        }
    };

    // Функция для открытия/закрытия меню действий над чатом
    const toggleMenu = (chatId, event) => {
        event.stopPropagation();
        
        if (showMenu === chatId) {
            // Если меню уже открыто для этого чата, закрываем его
            setShowMenu(null);
        } else {
            // Рассчитываем позицию меню с учетом размеров экрана
            const x = event.clientX;
            const y = event.clientY;
            
            // Проверяем, не выходит ли меню за правую границу экрана
            const menuWidth = 150; // Примерная ширина меню
            const menuHeight = 80; // Примерная высота меню
            const adjustedX = x + menuWidth > window.innerWidth ? window.innerWidth - menuWidth - 10 : x;
            const adjustedY = y + menuHeight > window.innerHeight ? y - menuHeight : y;
            
            setMenuPosition({ x: adjustedX, y: adjustedY });
            setShowMenu(chatId);
        }
    };

    // Функция для начала редактирования названия чата
    const startEditingTitle = (chatId, currentTitle, event) => {
        event.stopPropagation();
        setEditingTitle(chatId);
        setNewTitle(currentTitle);
        setShowMenu(null); // Закрываем меню после выбора опции
    };

    // Функция для сохранения нового названия чата
    const saveTitle = async (chatId) => {
        if (!newTitle.trim()) {
            setEditingTitle(null);
            return;
        }

        try {
            const response = await fetch(`${BASE_API_URL}/api/chats/${chatId}/rename`, {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ title: newTitle })
            });

            if (response.ok) {
                // После успешного сохранения обновляем список чатов
                if (loadUserConversations) {
                    loadUserConversations();
                }
                setEditingTitle(null);
            } else {
                console.error('Failed to save title:', response.status);
                // Показываем сообщение об ошибке пользователю
                alert('Не удалось сохранить название чата');
            }
        } catch (error) {
            console.error('Error saving title:', error);
            // Показываем сообщение об ошибке пользователю
            alert('Ошибка при сохранении названия чата');
        }
    };

    // Функция для отмены редактирования названия
    const cancelEditing = () => {
        setEditingTitle(null);
        setNewTitle('');
    };

    // Функция для удаления чата
    const deleteChat = async (chatId, event) => {
        event.stopPropagation();
        
        // Подтверждение удаления
        if (!window.confirm('Вы уверены, что хотите удалить этот чат?')) {
            setShowMenu(null);
            return;
        }

        try {
            const response = await fetch(`${BASE_API_URL}/api/chats/${chatId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Content-Type': 'application/json',
                }
            });

            if (response.ok) {
                // Если удаляемый чат является текущим, сбрасываем currentConversationId
                if (currentConversationId === chatId) {
                    setCurrentConversationId(null);
                }
                
                // После успешного удаления обновляем список чатов
                if (loadUserConversations) {
                    loadUserConversations();
                }
                
                setShowMenu(null);
            } else {
                console.error('Failed to delete chat:', response.status);
                // Показываем сообщение об ошибке пользователю
                alert('Не удалось удалить чат');
            }
        } catch (error) {
            console.error('Error deleting chat:', error);
            // Показываем сообщение об ошибке пользователю
            alert('Ошибка при удалении чата');
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
                {/* Отображаем список чатов */}
                {conversations && conversations.length > 0 ? (
                    conversations.map((chat) => (
                        <div
                            key={chat.id}
                            className={`chat-list-item ${currentConversationId === chat.id ? 'active' : ''}`}
                            onClick={() => setCurrentConversationId(chat.id)}
                        >
                            {editingTitle === chat.id ? (
                                // Режим редактирования названия
                                <div className="chat-title-edit">
                                    <input
                                        type="text"
                                        value={newTitle}
                                        onChange={(e) => setNewTitle(e.target.value)}
                                        onClick={(e) => e.stopPropagation()}
                                        autoFocus
                                    />
                                    <button onClick={(e) => { e.stopPropagation(); saveTitle(chat.id); }}>✓</button>
                                    <button onClick={(e) => { e.stopPropagation(); cancelEditing(); }}>✗</button>
                                </div>
                            ) : (
                                // Обычный режим отображения
                                <>
                                    <span className="chat-title">{chat.title}</span>
                                    <button 
                                        className="chat-menu-button"
                                        onClick={(e) => toggleMenu(chat.id, e)}
                                        ref={(el) => (menuButtonRef.current[chat.id] = el)}
                                    >
                                        ⋮
                                    </button>
                                </>
                            )}
                        </div>
                    ))
                ) : (
                    <div className="chat-list-item empty">
                        Нет чатов
                    </div>
                )}
            </div>
            
            {/* Меню действий над чатом, отображается поверх всех элементов */}
            {showMenu && (
                <div 
                    className="chat-menu" 
                    onClick={(e) => e.stopPropagation()}
                    style={{
                        position: 'fixed',
                        top: `${menuPosition.y}px`,
                        left: `${menuPosition.x}px`,
                        transform: 'translate(-100%, 0)', // Сдвигаем меню влево, чтобы оно не перекрывало кнопку
                        zIndex: 9999 // Максимальный z-index чтобы меню было поверх всех элементов
                    }}
                >
                    <button 
                        className="menu-item"
                        onClick={(e) => startEditingTitle(showMenu, conversations.find(c => c.id === showMenu)?.title || '', e)}
                    >
                        Изменить название
                    </button>
                    <button 
                        className="menu-item delete"
                        onClick={(e) => deleteChat(showMenu, e)}
                    >
                        Удалить чат
                    </button>
                </div>
            )}
        </nav>
    );
}

export default Sidebar;