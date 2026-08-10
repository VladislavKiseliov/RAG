import React from 'react';
import { useHomeDashboard } from '../hooks/useHomeDashboard';
import MockBadge from '../components/MockBadge.jsx';

function HomePage({ currentUser, onSelectSection }) {
    const home = useHomeDashboard();
    const showSearchResults = home.query.trim().length > 0;

    const dateLabel = new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' });

    return (
        <main className="home-main">
            <div className="home-header">
                <div>
                    <div className="home-greet-eyebrow">{dateLabel} <MockBadge title="Главная целиком на демо-данных — поиск, уведомления, напоминания и задачи не связаны с реальным бэкендом" /></div>
                    <div className="home-greet-title">{home.greeting}{currentUser?.name ? `, ${currentUser.name}` : ''}</div>
                </div>
                <div className="home-search">
                    <span>⌕</span>
                    <input
                        className="field"
                        value={home.query}
                        onChange={(e) => home.setQuery(e.target.value)}
                        placeholder="Искать по чатам, документам, заметкам…"
                    />
                </div>
                <div className="home-quicklinks">
                    {home.quickLinks.map((q) => (
                        <div key={q.section} className="home-quicklink" onClick={() => onSelectSection(q.section)}>
                            <span className="kb-accent">{q.icon}</span>
                            <span className="mono">{q.stat}</span>
                        </div>
                    ))}
                </div>
            </div>

            {showSearchResults ? (
                <div className="home-search-results">
                    {home.searchResults.map((r, i) => (
                        <div key={i} className="home-search-result" onClick={() => onSelectSection(r.section)}>
                            <span className="home-search-result-icon kb-accent">{r.icon}</span>
                            <div className="home-search-result-body">
                                <div className="home-search-result-title clamp1">{r.title}</div>
                                <div className="home-search-result-sub clamp1 kb-muted">{r.subtitle}</div>
                            </div>
                            <span className="mono kb-muted">{r.kindLabel}</span>
                        </div>
                    ))}
                    {home.searchResults.length === 0 && (
                        <div className="home-search-empty">Ничего не найдено по «{home.query}»</div>
                    )}
                </div>
            ) : (
                <div className="home-body">
                    <div className="home-col">
                        <div className="home-col-spacer" />
                        <div className="home-card home-notif-card">
                            <div className="home-card-header">
                                <span className="home-card-title">Уведомления</span>
                                <span className="mono kb-accent">{home.notifications.length} новых</span>
                            </div>
                            <div className="home-notif-list">
                                {home.notifications.map((nf, i) => (
                                    <div key={i} className="home-notif-item" onClick={() => onSelectSection(nf.section)}>
                                        <span className={`home-notif-dot home-notif-dot-${nf.kind}`} />
                                        <span className="home-notif-icon mono">{nf.icon}</span>
                                        <div className="home-notif-body">
                                            <div className="home-notif-text"><b>{nf.who}</b> {nf.text}</div>
                                            <div className="home-notif-when kb-muted">{nf.when}</div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="home-col">
                        <div className="home-col2-top">
                            <div className="home-card home-reminders-card">
                                <div className="home-card-header">
                                    <span className="home-card-title small">Напоминания</span>
                                    <span className="home-card-link kb-accent" onClick={() => onSelectSection('notes')}>Заметки →</span>
                                </div>
                                <div className="home-reminders-list">
                                    {home.reminders.map((r, i) => (
                                        <div key={i} className={`home-reminder-item${r.urgent ? ' urgent' : ''}`} onClick={() => onSelectSection('notes')}>
                                            <span>⏰</span>
                                            <div className="home-reminder-body">
                                                <div className="home-reminder-title clamp2">{r.title}</div>
                                                <div className={`home-reminder-due mono${r.urgent ? ' kb-accent' : ' kb-muted'}`}>{r.dueLabel}</div>
                                            </div>
                                        </div>
                                    ))}
                                    {home.reminders.length === 0 && (
                                        <div className="home-reminders-empty kb-muted">Нет активных напоминаний</div>
                                    )}
                                </div>
                            </div>
                        </div>

                        <div className="home-card home-tasks-card">
                            <div className="home-card-header">
                                <span className="home-card-title small">Мои задачи</span>
                                <span className="mono kb-muted">{home.myTasks.filter((t) => t.done).length}/{home.myTasks.length}</span>
                            </div>
                            <div className="home-tasks-list">
                                {home.myTasks.map((tk) => (
                                    <div key={tk.id} className="home-task-item" onClick={() => home.toggleTask(tk.id)}>
                                        <span className={`home-task-box${tk.done ? ' done' : ''}`}>{tk.done ? '✓' : ''}</span>
                                        <div className="home-task-body">
                                            <div className={`home-task-title clamp1${tk.done ? ' done' : ''}`}>{tk.title}</div>
                                            <div className="home-task-project mono kb-muted">{tk.project}</div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </main>
    );
}

export default HomePage;