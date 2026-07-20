import React, { useState, useCallback } from 'react';
import { useClickOutside } from '../hooks/useClickOutside';
import ProfileModal from './ProfileModal.jsx';

function UserMenu({ initials = '..', onLogout, theme, onToggleTheme, footerClassName = 'sidebar-footer' }) {
    const [showUserMenu, setShowUserMenu] = useState(false);
    const [showProfile, setShowProfile] = useState(false);

    useClickOutside(showUserMenu, ['.user-menu', '.user-menu-button'], useCallback(() => setShowUserMenu(false), []));

    return (
        <div className={footerClassName}>
            <button
                className="user-menu-button"
                onClick={() => setShowUserMenu((prev) => !prev)}
                aria-label="User menu"
            >
                <span className="user-menu-avatar">{initials}</span>
            </button>
            {showUserMenu && (
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
            )}
            {showProfile && (
                <ProfileModal onClose={() => setShowProfile(false)} />
            )}
        </div>
    );
}

export default UserMenu;