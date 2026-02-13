// src/components/Sidebar.js

import React, { useState, useEffect, useRef } from 'react';
import { BASE_API_URL, ENDPOINTS } from '../config/api';

function Sidebar({ currentConversationId, setCurrentConversationId, conversations, loadUserConversations, getAccessToken, onLogout, onToggleSidebar, isCollapsed, theme, onToggleTheme }) {
    // РЎРѕСЃС‚РѕСЏРЅРёСЏ РґР»СЏ СѓРїСЂР°РІР»РµРЅРёСЏ РјРµРЅСЋ РґРµР№СЃС‚РІРёР№ РЅР°Рґ С‡Р°С‚РѕРј
    const [showMenu, setShowMenu] = useState(null); // null РёР»Рё ID С‡Р°С‚Р°, РґР»СЏ РєРѕС‚РѕСЂРѕРіРѕ РѕС‚РєСЂС‹С‚Рѕ РјРµРЅСЋ
    const [menuPosition, setMenuPosition] = useState({ x: 0, y: 0 }); // РџРѕР·РёС†РёСЏ РјРµРЅСЋ
    const [editingTitle, setEditingTitle] = useState(null); // null РёР»Рё ID С‡Р°С‚Р°, РєРѕС‚РѕСЂС‹Р№ СЂРµРґР°РєС‚РёСЂСѓРµС‚СЃСЏ
    const [newTitle, setNewTitle] = useState(''); // РќРѕРІРѕРµ РЅР°Р·РІР°РЅРёРµ С‡Р°С‚Р° РїСЂРё СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёРё
    const [error, setError] = useState(null); // РЎРѕСЃС‚РѕСЏРЅРёРµ РґР»СЏ РѕС‚РѕР±СЂР°Р¶РµРЅРёСЏ РѕС€РёР±РѕРє
    const [loading, setLoading] = useState(false); // РЎРѕСЃС‚РѕСЏРЅРёРµ Р·Р°РіСЂСѓР·РєРё
    const [showUserMenu, setShowUserMenu] = useState(false); // РњРµРЅСЋ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
    const menuButtonRef = useRef({}); // Р РµС„С‹ РґР»СЏ РєРЅРѕРїРѕРє РјРµРЅСЋ

    // Р¤СѓРЅРєС†РёСЏ РґР»СЏ Р·Р°РєСЂС‹С‚РёСЏ РјРµРЅСЋ РїСЂРё РєР»РёРєРµ РІРЅРµ РµРіРѕ РѕР±Р»Р°СЃС‚Рё
    useEffect(() => {
        const handleClickOutside = (event) => {
            // РџСЂРѕРІРµСЂСЏРµРј, Р±С‹Р» Р»Рё РєР»РёРє РІРЅРµ РјРµРЅСЋ
            if (showMenu && !event.target.closest('.chat-menu') && !event.target.closest('.chat-menu-button')) {
                setShowMenu(null);
            }
            if (showUserMenu && !event.target.closest('.user-menu') && !event.target.closest('.user-menu-button')) {
                setShowUserMenu(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [showMenu, showUserMenu]);

    // Р¤СѓРЅРєС†РёСЏ РґР»СЏ РѕС‚РѕР±СЂР°Р¶РµРЅРёСЏ СЃРѕРѕР±С‰РµРЅРёСЏ РѕР± РѕС€РёР±РєРµ
    const showError = (message) => {
        setError(message);
        setTimeout(() => setError(null), 5000); // РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРё СЃРєСЂС‹С‚СЊ РѕС€РёР±РєСѓ С‡РµСЂРµР· 5 СЃРµРєСѓРЅРґ
    };

    const handleProfile = () => {
        alert('Профиль: функционал в разработке.');
    };

    const handleHelp = () => {
        alert('Справка: это базовая база знаний. Добавим статьи и поиск позже.');
    };

    // Р¤СѓРЅРєС†РёСЏ РґР»СЏ СЃРѕР·РґР°РЅРёСЏ РЅРѕРІРѕРіРѕ С‡Р°С‚Р°
    const handleNewChat = async () => {
        setLoading(true);
        setError(null);
        try {
            const token = await getAccessToken();
            if (!token) {
                showError('Сессия истекла. Войдите снова.');
                setLoading(false);
                return;
            }
            const response = await fetch(BASE_API_URL + ENDPOINTS.CONVERSATIONS, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
            });

            if (response.ok) {
                const data = await response.json();
                // РЈСЃС‚Р°РЅР°РІР»РёРІР°РµРј РЅРѕРІС‹Р№ С‡Р°С‚ РєР°Рє С‚РµРєСѓС‰РёР№
                setCurrentConversationId(data.conversation_id);
                // РћР±РЅРѕРІР»СЏРµРј СЃРїРёСЃРѕРє С‡Р°С‚РѕРІ РїРѕСЃР»Рµ СЃРѕР·РґР°РЅРёСЏ РЅРѕРІРѕРіРѕ
                if (loadUserConversations) {
                    loadUserConversations();
                }
            } else {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.detail || `Failed to create new chat: ${response.status}`;
                console.error(errorMessage);
                showError(errorMessage);
            }
        } catch (error) {
            console.error('Network error when creating new chat:', error);
            showError('Network error when creating new chat. Please check your connection.');
        } finally {
            setLoading(false);
        }
    };

    // Р¤СѓРЅРєС†РёСЏ РґР»СЏ РѕС‚РєСЂС‹С‚РёСЏ/Р·Р°РєСЂС‹С‚РёСЏ РјРµРЅСЋ РґРµР№СЃС‚РІРёР№ РЅР°Рґ С‡Р°С‚РѕРј
    const toggleMenu = (chatId, event) => {
        event.stopPropagation();
        
        if (showMenu === chatId) {
            // Р•СЃР»Рё РјРµРЅСЋ СѓР¶Рµ РѕС‚РєСЂС‹С‚Рѕ РґР»СЏ СЌС‚РѕРіРѕ С‡Р°С‚Р°, Р·Р°РєСЂС‹РІР°РµРј РµРіРѕ
            setShowMenu(null);
        } else {
            // Р Р°СЃСЃС‡РёС‚С‹РІР°РµРј РїРѕР·РёС†РёСЋ РјРµРЅСЋ СЃ СѓС‡РµС‚РѕРј СЂР°Р·РјРµСЂРѕРІ СЌРєСЂР°РЅР°
            const x = event.clientX;
            const y = event.clientY;
            
            // РџСЂРѕРІРµСЂСЏРµРј, РЅРµ РІС‹С…РѕРґРёС‚ Р»Рё РјРµРЅСЋ Р·Р° РїСЂР°РІСѓСЋ РіСЂР°РЅРёС†Сѓ СЌРєСЂР°РЅР°
            const menuWidth = 150; // РџСЂРёРјРµСЂРЅР°СЏ С€РёСЂРёРЅР° РјРµРЅСЋ
            const menuHeight = 80; // РџСЂРёРјРµСЂРЅР°СЏ РІС‹СЃРѕС‚Р° РјРµРЅСЋ
            const adjustedX = x + menuWidth > window.innerWidth ? window.innerWidth - menuWidth - 10 : x;
            const adjustedY = y + menuHeight > window.innerHeight ? y - menuHeight : y;
            
            setMenuPosition({ x: adjustedX, y: adjustedY });
            setShowMenu(chatId);
        }
    };

    // Р¤СѓРЅРєС†РёСЏ РґР»СЏ РЅР°С‡Р°Р»Р° СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёСЏ РЅР°Р·РІР°РЅРёСЏ С‡Р°С‚Р°
    const startEditingTitle = (chatId, currentTitle, event) => {
        event.stopPropagation();
        setEditingTitle(chatId);
        setNewTitle(currentTitle);
        setShowMenu(null); // Р—Р°РєСЂС‹РІР°РµРј РјРµРЅСЋ РїРѕСЃР»Рµ РІС‹Р±РѕСЂР° РѕРїС†РёРё
    };

    // Р¤СѓРЅРєС†РёСЏ РґР»СЏ СЃРѕС…СЂР°РЅРµРЅРёСЏ РЅРѕРІРѕРіРѕ РЅР°Р·РІР°РЅРёСЏ С‡Р°С‚Р°
    const saveTitle = async (chatId) => {
        if (!newTitle.trim()) {
            setEditingTitle(null);
            return;
        }

        setLoading(true);
        try {
            const token = await getAccessToken();
            if (!token) {
                showError('Сессия истекла. Войдите снова.');
                setLoading(false);
                return;
            }
            const response = await fetch(`${BASE_API_URL}/api/chats/${chatId}/rename`, {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ title: newTitle })
            });

            if (response.ok) {
                // РџРѕСЃР»Рµ СѓСЃРїРµС€РЅРѕРіРѕ СЃРѕС…СЂР°РЅРµРЅРёСЏ РѕР±РЅРѕРІР»СЏРµРј СЃРїРёСЃРѕРє С‡Р°С‚РѕРІ
                if (loadUserConversations) {
                    loadUserConversations();
                }
                setEditingTitle(null);
            } else {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.detail || `Failed to save title: ${response.status}`;
                console.error(errorMessage);
                showError(errorMessage);
            }
        } catch (error) {
            console.error('Network error when saving title:', error);
            showError('Network error when saving title. Please check your connection.');
        } finally {
            setLoading(false);
        }
    };

    // Р¤СѓРЅРєС†РёСЏ РґР»СЏ РѕС‚РјРµРЅС‹ СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёСЏ РЅР°Р·РІР°РЅРёСЏ
    const cancelEditing = () => {
        setEditingTitle(null);
        setNewTitle('');
    };

    // Р¤СѓРЅРєС†РёСЏ РґР»СЏ СѓРґР°Р»РµРЅРёСЏ С‡Р°С‚Р°
    const deleteChat = async (chatId, event) => {
        event.stopPropagation();
        
        // РџРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ СѓРґР°Р»РµРЅРёСЏ
        if (!window.confirm('Вы уверены, что хотите удалить этот чат?')) {
            setShowMenu(null);
            return;
        }

        setLoading(true);
        try {
            const token = await getAccessToken();
            if (!token) {
                showError('Сессия истекла. Войдите снова.');
                setLoading(false);
                return;
            }
            const response = await fetch(`${BASE_API_URL}/api/chats/${chatId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                }
            });

            if (response.ok) {
                // Р•СЃР»Рё СѓРґР°Р»СЏРµРјС‹Р№ С‡Р°С‚ СЏРІР»СЏРµС‚СЃСЏ С‚РµРєСѓС‰РёРј, СЃР±СЂР°СЃС‹РІР°РµРј currentConversationId
                if (currentConversationId === chatId) {
                    setCurrentConversationId(null);
                }
                
                // РџРѕСЃР»Рµ СѓСЃРїРµС€РЅРѕРіРѕ СѓРґР°Р»РµРЅРёСЏ РѕР±РЅРѕРІР»СЏРµРј СЃРїРёСЃРѕРє С‡Р°С‚РѕРІ
                if (loadUserConversations) {
                    loadUserConversations();
                }
                
                setShowMenu(null);
            } else {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.detail || `Failed to delete chat: ${response.status}`;
                console.error(errorMessage);
                showError(errorMessage);
            }
        } catch (error) {
            console.error('Network error when deleting chat:', error);
            showError('Network error when deleting chat. Please check your connection.');
        } finally {
            setLoading(false);
        }
    };

    if (isCollapsed) {
        return (
            <nav className="sidebar compact">
                <div className="sidebar-top">
                    <button
                        className="icon-btn"
                        onClick={() => onToggleSidebar?.()}
                        aria-label="Развернуть панель"
                        title="Скрыть/Показать панель"
                        disabled={loading}
                    >
                        <span className="toggle-sidebar-icon">🔖</span>
                    </button>
                </div>
                <div className="compact-controls">
                    <button
                        className="icon-btn"
                        onClick={handleNewChat}
                        aria-label="Новый чат"
                        title="Новый чат"
                        disabled={loading}
                    >
                        +
                    </button>
                </div>
                <div className="compact-footer">
                    <button
                        className="user-menu-button"
                        onClick={() => setShowUserMenu((prev) => !prev)}
                        aria-label="User menu"
                        disabled={loading}
                    >
                        <span className="user-menu-avatar">RG</span>
                    </button>
                    {showUserMenu && (
                        <div className="user-menu" onClick={(e) => e.stopPropagation()}>
                            <button className="menu-item" onClick={handleProfile} disabled={loading}>
                                Профиль
                            </button>
                            <button className="menu-item" onClick={handleHelp} disabled={loading}>
                                Справка
                            </button>
                            <button className="menu-item" onClick={() => onToggleTheme?.()} disabled={loading}>
                                Тема: {theme === 'light' ? 'Светлая' : 'Темная'}
                            </button>
                            <button className="menu-item" onClick={() => onLogout?.(true)} disabled={loading}>
                                Выйти
                            </button>
                            <button className="menu-item" disabled={loading}>
                                Настройки
                            </button>
                        </div>
                    )}
                </div>
            </nav>
        );
    }

    return (
        <nav className="sidebar">
            <div className="sidebar-top">
                <button className="icon-btn" onClick={() => onToggleSidebar?.()} disabled={loading} aria-label="Свернуть панель" title="Скрыть/Показать панель">
                    <span className="toggle-sidebar-icon">🔖</span>
                </button>
            </div>
            <div className="sidebar-header">
                <button className="new-chat-btn" id="newChatBtn" onClick={handleNewChat} disabled={loading}>
                    <span className="new-chat-icon">+</span>
                    {loading ? 'Создание...' : 'Новый чат'}
                </button>
                <div className="chat-section-title">Чаты</div>
            </div>
            
            {/* РћС‚РѕР±СЂР°Р¶РµРЅРёРµ РѕС€РёР±РѕРє */}
            {error && (
                <div className="error-message" style={{ 
                    color: 'red', 
                    padding: '10px', 
                    margin: '10px', 
                    border: '1px solid red', 
                    borderRadius: '4px',
                    backgroundColor: '#ffe6e6'
                }}>
                    {error}
                </div>
            )}
            
            <div className="chat-list" id="chatList">
                {/* РћС‚РѕР±СЂР°Р¶Р°РµРј СЃРїРёСЃРѕРє С‡Р°С‚РѕРІ */}
                {conversations && conversations.length > 0 ? (
                    conversations.map((chat) => (
                        <div
                            key={chat.id}
                            className={`chat-list-item ${currentConversationId === chat.id ? 'active' : ''}`}
                            onClick={() => setCurrentConversationId(chat.id)}
                        >
                            {editingTitle === chat.id ? (
                                // Р РµР¶РёРј СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёСЏ РЅР°Р·РІР°РЅРёСЏ
                                <div className="chat-title-edit">
                                    <input
                                        type="text"
                                        value={newTitle}
                                        onChange={(e) => setNewTitle(e.target.value)}
                                        onClick={(e) => e.stopPropagation()}
                                        autoFocus
                                    />
                                    <div className="edit-actions">
                                        <button className="save" onClick={(e) => { e.stopPropagation(); saveTitle(chat.id); }} disabled={loading}>
                                            {loading ? 'Сохранение...' : '✓'}
                                        </button>
                                        <button className="cancel" onClick={(e) => { e.stopPropagation(); cancelEditing(); }} disabled={loading}>
                                            ✕
                                        </button>
                                    </div>
                                </div>
                            ) : (
                                // РћР±С‹С‡РЅС‹Р№ СЂРµР¶РёРј РѕС‚РѕР±СЂР°Р¶РµРЅРёСЏ
                                <>
                                    <span className="chat-title">{chat.title}</span>
                                    <button
                                        className="chat-menu-button"
                                        onClick={(e) => toggleMenu(chat.id, e)}
                                        ref={(el) => (menuButtonRef.current[chat.id] = el)}
                                        disabled={loading}
                                        aria-label="Chat menu"
                                    >
                                        <span>&#8942;</span>
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
            
            {/* РњРµРЅСЋ РґРµР№СЃС‚РІРёР№ РЅР°Рґ С‡Р°С‚РѕРј, РѕС‚РѕР±СЂР°Р¶Р°РµС‚СЃСЏ РїРѕРІРµСЂС… РІСЃРµС… СЌР»РµРјРµРЅС‚РѕРІ */}
            {showMenu && (
                <div 
                    className="chat-menu" 
                    onClick={(e) => e.stopPropagation()}
                    style={{
                        position: 'fixed',
                        top: `${menuPosition.y}px`,
                        left: `${menuPosition.x}px`,
                        transform: 'translate(-100%, 0)', // РЎРґРІРёРіР°РµРј РјРµРЅСЋ РІР»РµРІРѕ, С‡С‚РѕР±С‹ РѕРЅРѕ РЅРµ РїРµСЂРµРєСЂС‹РІР°Р»Рѕ РєРЅРѕРїРєСѓ
                        zIndex: 9999 // РњР°РєСЃРёРјР°Р»СЊРЅС‹Р№ z-index С‡С‚РѕР±С‹ РјРµРЅСЋ Р±С‹Р»Рѕ РїРѕРІРµСЂС… РІСЃРµС… СЌР»РµРјРµРЅС‚РѕРІ
                    }}
                >
                    <button 
                        className="menu-item"
                        onClick={(e) => startEditingTitle(showMenu, conversations.find(c => c.id === showMenu)?.title || '', e)}
                        disabled={loading}
                    >
                        Изменить название
                    </button>
                    <button 
                        className="menu-item delete"
                        onClick={(e) => deleteChat(showMenu, e)}
                        disabled={loading}
                    >
                        Удалить чат
                    </button>
                </div>
            )}

            <div className="sidebar-footer">
                <button
                    className="user-menu-button"
                    onClick={() => setShowUserMenu((prev) => !prev)}
                    aria-label="User menu"
                    disabled={loading}
                >
                    <span className="user-menu-avatar">RG</span>
                </button>
                {showUserMenu && (
                    <div className="user-menu" onClick={(e) => e.stopPropagation()}>
                        <button className="menu-item" onClick={handleProfile} disabled={loading}>
                            Профиль
                        </button>
                        <button className="menu-item" onClick={handleHelp} disabled={loading}>
                            Справка
                        </button>
                        <button className="menu-item" onClick={() => onToggleTheme?.()} disabled={loading}>
                            Тема: {theme === 'light' ? 'Светлая' : 'Темная'}
                        </button>
                        <button className="menu-item" onClick={() => onLogout?.(true)} disabled={loading}>
                            Выйти
                        </button>
                        <button className="menu-item" disabled={loading}>
                            Настройки
                        </button>
                    </div>
                )}
            </div>
        </nav>
    );
}

export default Sidebar;




















