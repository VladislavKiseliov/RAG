import React from 'react';

function QueueView({ proj }) {
    const project = proj.projects.find((p) => p.id === proj.selectedProjectId);
    if (!project) return null;

    const pending = proj.projectChangesets(project.id).filter((c) => c.status === 'pending');

    return (
        <main className="proj-detail-shell">
            <div className="proj-detail-center">
                <header className="proj-detail-header">
                    <div className="proj-back" onClick={proj.backToOverview}>← {project.name}</div>
                    <div className="proj-detail-title-row"><div className="proj-detail-name">Очередь на утверждение</div></div>
                </header>

                <div className="proj-detail-body">
                    {pending.length === 0 ? (
                        <div className="proj-empty-state">Нет пакетов, ожидающих утверждения.</div>
                    ) : (
                        <div className="proj-queue-list">
                            {pending.map((cs) => {
                                const conflict = proj.changesetConflict(cs);
                                return (
                                    <div key={cs.id} className="proj-queue-card">
                                        <div className="proj-queue-card-head">
                                            <div className="proj-member-chip">{cs.authorInit}</div>
                                            <div style={{ flex: 1 }}>
                                                <div className="proj-activity-text">{cs.comment}</div>
                                                <div className="kb-muted proj-activity-when">{cs.author} · {cs.date}</div>
                                            </div>
                                        </div>
                                        {conflict && (
                                            <div className="proj-conflict-banner">
                                                ⚠ Версия документа изменилась с момента отправки пакета — сверьте перед утверждением.
                                            </div>
                                        )}
                                        <div className="proj-queue-items">
                                            {cs.items.map((it, i) => (
                                                <div key={i} className="proj-queue-item" onClick={() => it.docId && proj.openDoc(it.docId)}>
                                                    <span className="mono">{it.code}</span>
                                                    <span>{it.name}</span>
                                                    <span className="kb-muted">{it.action === 'new' ? 'новый документ' : `замена v${it.fromVersion} →`}</span>
                                                </div>
                                            ))}
                                        </div>
                                        <div className="proj-queue-actions">
                                            <div className="proj-new-btn" onClick={() => proj.approveChangeset(cs.id)}>Утвердить</div>
                                            <div className="proj-reject-btn" onClick={() => proj.openReject(cs.id)}>Отклонить</div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>
        </main>
    );
}

export default QueueView;
