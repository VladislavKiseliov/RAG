import React, { useState, useEffect } from 'react';
import ProfileModal from './ProfileModal.jsx';
import { ENDPOINTS } from '../config/api';

const getInitials = (login) => {
    const parts = login.split(/[_\-.]/).filter(Boolean);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return login.slice(0, 2).toUpperCase();
};

function UserMenu({ api, onLogout, theme, onToggleTheme, footerClassName = 'sidebar-footer' }) {
    const [showUserMenu, setShowUserMenu] = useState(false);
    const [showProfile, setShowProfile] = useState(false);
    const [initials, setInitials] = useState('...');

    useEffect(() => {
        api.get(ENDPOINTS.PROFILE)
            .then((data) => { if (data.login) setInitials(getInitials(data.login)); })
            .catch(() => {});
    }, []);

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (showUserMenu && !event.target.closest('.user-menu') && !event.target.closest('.user-menu-button')) {
                setShowUserMenu(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [showUserMenu]);

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
                <ProfileModal api={api} onClose={() => setShowProfile(false)} />
            )}
        </div>
    );
}

export default UserMenu;