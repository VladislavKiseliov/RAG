import React from 'react';

function StatsTab({ admin }) {
    const docsTotal = admin.documents.length;
    const pointsValues = admin.documents.map((d) => d.points).filter((v) => v != null);
    const pointsTotal = pointsValues.length ? pointsValues.reduce((a, b) => a + b, 0) : null;
    const usersTotal = admin.users.length;
    const tasksQueued = admin.tasks.filter((t) => t.state === 'running' || t.state === 'queued').length;

    const top = [...admin.documents].filter((d) => d.points != null).sort((a, b) => b.points - a.points).slice(0, 6);
    const max = top[0]?.points || 1;

    return (
        <div>
            <div className="adm-stats-grid">
                <div className="adm-stat-card"><div className="mono adm-stat-value">{docsTotal}</div><div className="adm-stat-label">Документов</div></div>
                <div className="adm-stat-card"><div className="mono adm-stat-value">{pointsTotal ?? '—'}</div><div className="adm-stat-label">Точек в БД</div></div>
                <div className="adm-stat-card"><div className="mono adm-stat-value">{usersTotal}</div><div className="adm-stat-label">Активных пользователей</div></div>
                <div className="adm-stat-card"><div className="mono adm-stat-value">{tasksQueued}</div><div className="adm-stat-label">Задач в очереди</div></div>
            </div>

            <div className="adm-card">
                <div className="adm-card-title">Топ документов по числу точек</div>
                <div className="adm-bar-list">
                    {top.map((d) => (
                        <div key={d.id} className="adm-bar-row">
                            <span className="adm-bar-label">{d.title}</span>
                            <div className="adm-bar-track"><div className="adm-bar-fill" style={{ width: `${(d.points / max) * 100}%` }} /></div>
                            <span className="mono adm-bar-value">{d.points}</span>
                        </div>
                    ))}
                    {top.length === 0 && <div className="kb-muted">Нет данных</div>}
                </div>
            </div>
        </div>
    );
}

export default StatsTab;