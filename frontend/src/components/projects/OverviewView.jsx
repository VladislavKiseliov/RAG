import React from 'react';

const STATUS_CLASS = { active: 'ok', review: 'accent', plan: 'muted' };

function OverviewView({ proj, onAskAi }) {
    const project = proj.projects.find((p) => p.id === proj.selectedProjectId);
    if (!project) return null;

    const pending = proj.pendingCount(project.id);
    const myChangesets = proj.projectChangesets(project.id).filter((c) => c.author === proj.currentUser() && c.status === 'pending');

    return (
        <main className="proj-detail-shell">
            <div className="proj-detail-center">
                <header className="proj-detail-header">
                    <div className="proj-back" onClick={proj.back}>← Все проекты</div>
                    <div className="proj-detail-title-row">
                        <div className="proj-card-glyph large">{project.glyph}</div>
                        <div>
                            <div className="proj-detail-name">{project.name}</div>
                            <div className="proj-detail-meta">
                                <span className={`proj-status-dot ${STATUS_CLASS[project.kind] || 'muted'}`} />
                                <span>{project.status} · {project.type} · {project.lead}</span>
                            </div>
                        </div>
                        <div className="proj-chat-link" onClick={proj.goFiles} style={{ marginLeft: 'auto' }}>▤ Файлы проекта</div>
                        <div className="proj-chat-link" onClick={onAskAi}><span className="kb-accent">✦</span> Спросить AI по проекту</div>
                        <div className="proj-chat-link" onClick={proj.goArchive}>Архив версий</div>
                    </div>
                </header>

                <div className="proj-detail-body">
                    <div className="proj-detail-desc">{project.desc}</div>

                    {proj.role === 'manager' ? (
                        pending > 0 && (
                            <div className="proj-queue-widget" onClick={proj.goQueue}>
                                Ждут утверждения: {pending}
                            </div>
                        )
                    ) : (
                        <div style={{ marginTop: 22 }}>
                            <div className="kb-aside-group-title">Ваши пакеты изменений</div>
                            {myChangesets.length === 0 ? (
                                <div className="kb-muted" style={{ fontSize: 13 }}>Нет пакетов на утверждении.</div>
                            ) : (
                                <div className="proj-task-list">
                                    {myChangesets.map((cs) => (
                                        <div key={cs.id} className="proj-task-item" onClick={() => {
                                            const first = cs.items[0];
                                            if (first?.docId) proj.openDoc(first.docId); else proj.goFiles();
                                        }}>
                                            <span className="proj-status-dot accent" />
                                            <span className="proj-task-text">{cs.comment}</span>
                                            <span className="mono kb-muted proj-task-assignee">на утверждении</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    <div className="kb-aside-group-title" style={{ marginTop: 26 }}>Активность</div>
                    <div className="proj-activity-list">
                        {project.activity.map((a, i) => (
                            <div key={i} className="proj-activity-item">
                                <div className="proj-member-chip">{a.who}</div>
                                <div>
                                    <div className="proj-activity-text">{a.text}</div>
                                    <div className="kb-muted proj-activity-when">{a.when}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </main>
    );
}

export default OverviewView;
