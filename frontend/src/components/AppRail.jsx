import React from 'react';
import UserMenu from './UserMenu.jsx';

const SECTIONS = [
    { id: 'home', icon: '⌂', title: 'Главная' },
    { id: 'chats', icon: '✦', title: 'Чаты' },
    { id: 'knowledge', icon: '▤', title: 'База знаний' },
    { id: 'projects', icon: '◫', title: 'Проекты' },
    { id: 'notes', icon: '✎', title: 'Заметки' },
    { id: 'tasks', icon: '☑', title: 'Задачи на день' },
];

const ADMIN_SECTION = { id: 'admin', icon: '⚙', title: 'Админ-панель' };

function AppRail({ activeSection, onSelectSection, theme, onToggleTheme, isAdmin, onLogout, currentUser }) {
    const sections = isAdmin ? [...SECTIONS, ADMIN_SECTION] : SECTIONS;
    return (
        <nav className="app-rail">
            <div className="app-rail-logo">И</div>
            {sections.map((s) => (
                <div
                    key={s.id}
                    title={s.title}
                    className={`app-rail-icon${activeSection === s.id ? ' active' : ''}`}
                    onClick={() => onSelectSection(s.id)}
                >
                    {s.icon}
                </div>
            ))}
            <UserMenu
                initials={currentUser?.initials}
                onLogout={onLogout}
                theme={theme}
                onToggleTheme={onToggleTheme}
                footerClassName="compact-footer"
            />
        </nav>
    );
}

export default AppRail;
