import React, { useState, useCallback } from 'react';
import { useClickOutside } from '../hooks/useClickOutside';
import ProfileModal from './ProfileModal.jsx';

function UserMenu({ currentUser, onLogout, theme, onToggleTheme, footerClassName = 'sidebar-footer' }) {
    const [showUserMenu, setShowUserMenu] = useState(false);
    const [showProfile, setShowProfile] = useState(false);
    const userInfo = currentUser ?? { initials: '..', name: '', login: '', role: '' };

    useClickOutside(showUserMenu, ['.user-rich-menu', '.user-menu-button'], useCallback(() => setShowUserMenu(false), []));

    return (
        <div className={footerClassName}>
            <button
                className="user-menu-button"
                onClick={() => setShowUserMenu((prev) => !prev)}
                aria-label="User menu"
            >
                <span className="user-menu-avatar">{userInfo.initials}</span>
            </button>
            {showUserMenu && (
                <div className="user-rich-menu" onClick={(e) => e.stopPropagation()}>
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
                            onClick={() => { setShowUserMenu(false); setShowProfile(true); }}
                        >
                            <span className="item-left"><span className="item-icon">◴</span> Профиль и данные</span>
                        </button>
                        <button
                            className="profile-dropdown-item"
                            onClick={() => alert('Справка: это базовая база знаний.')}
                        >
                            <span className="item-left"><span className="item-icon">?</span> Справка</span>
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
                        <button className="profile-dropdown-item" disabled>
                            <span className="item-left"><span className="item-icon">⚙</span> Настройки</span>
                        </button>
                        <div className="profile-dropdown-divider" />
                        <button
                            className="profile-dropdown-item danger"
                            onClick={() => { setShowUserMenu(false); onLogout?.(true); }}
                        >
                            <span className="item-left"><span>⎋</span> Выйти</span>
                        </button>
                    </div>
                </div>
            )}
            {showProfile && (
                <ProfileModal onClose={() => setShowProfile(false)} />
            )}
        </div>
    );
}

export default UserMenu;