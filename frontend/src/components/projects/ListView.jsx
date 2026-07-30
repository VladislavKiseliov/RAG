import React from 'react';

const STATUS_CLASS = { active: 'ok', review: 'accent', plan: 'muted' };

function ListView({ proj, onNewProject }) {
    const { projects, pendingCount, role } = proj;
    const statActive = projects.filter((p) => p.kind === 'active').length;
    const statPending = projects.reduce((a, p) => a + pendingCount(p.id), 0);
    const statRejected = projects.reduce(
        (a, p) => a + proj.projectChangesets(p.id).filter((c) => c.status === 'rejected').length, 0,
    );

    return (
        <main className="proj-main">
            <header className="proj-header">
                <div className="proj-header-row">
                    <div>
                        <div className="proj-eyebrow">Рабочее пространство</div>
                        <div className="proj-title">Проекты</div>
                    </div>
                    <div className="proj-new-btn" onClick={onNewProject}><span>＋</span> Новый проект</div>
                </div>

                <div className="proj-stats-strip">
                    <div className="proj-stat-card"><div className="mono proj-stat-value accent">{projects.length}</div><div className="proj-stat-label">проектов на вас</div></div>
                    <div className="proj-stat-card"><div className="mono proj-stat-value">{statActive}</div><div className="proj-stat-label">в активной работе</div></div>
                    <div className="proj-stat-card"><div className="mono proj-stat-value" style={{ color: statPending > 0 ? 'var(--accent)' : undefined }}>{statPending}</div><div className="proj-stat-label">пакетов на утверждении</div></div>
                    <div className="proj-stat-card"><div className="mono proj-stat-value" style={{ color: statRejected > 0 ? '#d65f5f' : undefined }}>{statRejected}</div><div className="proj-stat-label">отклонённых пакетов</div></div>
                </div>
            </header>

            <div className="proj-content">
                <div className="kb-aside-group-title">Ваши проекты</div>
                <div className="proj-grid">
                    {projects.map((p) => {
                        const docsCount = proj.projectDocs(p.id).length;
                        const pending = pendingCount(p.id);
                        return (
                            <div key={p.id} className="proj-card" onClick={() => proj.openProject(p.id)}>
                                <div className="proj-card-top">
                                    <div className="proj-card-glyph">{p.glyph}</div>
                                    <div className="proj-card-name-wrap">
                                        <div className="proj-card-name">{p.name}</div>
                                        <div className="proj-card-status">
                                            <span className={`proj-status-dot ${STATUS_CLASS[p.kind] || 'muted'}`} />
                                            {p.status} · {p.lead}
                                        </div>
                                    </div>
                                    {role === 'manager' && pending > 0 && (
                                        <span className="proj-pending-badge">ждут утверждения: {pending}</span>
                                    )}
                                </div>
                                <div className="proj-card-desc clamp2">{p.desc}</div>
                                <div className="proj-card-footer">
                                    <div className="proj-card-members">
                                        {p.members.map((m, i) => <div key={i} className="proj-member-chip">{m.init}</div>)}
                                    </div>
                                    <span className="mono kb-muted">▤ {docsCount}</span>
                                    <span className="mono kb-muted proj-card-updated">{p.updated}</span>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </main>
    );
}

export default ListView;
