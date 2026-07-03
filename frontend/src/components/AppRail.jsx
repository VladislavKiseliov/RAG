import React from 'react';

const SECTIONS = [
    { id: 'chats', icon: '✦', title: 'Чаты' },
    { id: 'knowledge', icon: '▤', title: 'База знаний' },
    { id: 'projects', icon: '◫', title: 'Проекты' },
];

function AppRail({ activeSection, onSelectSection, theme, onToggleTheme }) {
    return (
        <nav className="app-rail">
            <div className="app-rail-logo">И</div>
            {SECTIONS.map((s) => (
                <div
                    key={s.id}
                    title={s.title}
                    className={`app-rail-icon${activeSection === s.id ? ' active' : ''}`}
                    onClick={() => onSelectSection(s.id)}
                >
                    {s.icon}
                </div>
            ))}
            <div
                className="app-rail-icon app-rail-theme"
                title="Тема"
                onClick={onToggleTheme}
            >
                {theme === 'dark' ? '☾' : '☀'}
            </div>
        </nav>
    );
}

export default AppRail;
