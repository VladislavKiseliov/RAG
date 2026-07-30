import React, { useState } from 'react';

function DocumentView({ proj, onAskAi }) {
    const doc = proj.docs.find((d) => d.id === proj.selectedDocId);
    const [noteDraft, setNoteDraft] = useState('');
    if (!doc) return null;

    const badge = proj.docBadge(doc);
    const rejectedCs = doc.lastRejectedChangesetId ? proj.changesets.find((c) => c.id === doc.lastRejectedChangesetId) : null;
    const lastVersion = doc.versions[doc.versions.length - 1];

    const handleAddNote = () => {
        if (!noteDraft.trim()) return;
        proj.addNote(doc.id, noteDraft);
        setNoteDraft('');
    };

    return (
        <main className="proj-detail-shell">
            <div className="proj-detail-center">
                <header className="proj-detail-header">
                    <div className="proj-back" onClick={proj.backToFiles}>← {doc.code}</div>
                    <div className="proj-detail-title-row">
                        <div>
                            <div className="proj-detail-name">{doc.name}</div>
                            <div className="proj-detail-meta">
                                <span className="proj-status-dot" style={{ background: badge.color }} />
                                <span>{badge.label} · {doc.code}</span>
                            </div>
                        </div>
                        <div className="proj-chat-link" style={{ marginLeft: 'auto' }} onClick={onAskAi}>
                            <span className="kb-accent">✦</span> Обсудить
                        </div>
                    </div>
                </header>

                <div className="proj-detail-body">
                    {rejectedCs && (
                        <div className="proj-rejected-banner">
                            <div><strong>Пакет отклонён:</strong> {rejectedCs.rejectionComment}</div>
                            <div className="proj-new-btn" onClick={() => proj.resubmitDoc(doc.id)}>Отправить исправленный пакет</div>
                        </div>
                    )}
                    {doc.pendingChangesetId && (
                        <div className="proj-pending-banner">Пакет изменений отправлен и ожидает утверждения.</div>
                    )}

                    {lastVersion && (
                        <div className="proj-doc-preview" onClick={() => proj.openPdf(doc.name)}>
                            📄 {lastVersion.fileName} — открыть предпросмотр
                        </div>
                    )}

                    <div className="kb-aside-group-title" style={{ marginTop: 22 }}>История версий</div>
                    {doc.versions.length === 0 ? (
                        <div className="kb-muted" style={{ fontSize: 13 }}>Версий пока нет.</div>
                    ) : (
                        <table className="proj-files-table">
                            <thead><tr><th>Версия</th><th>Файл</th><th>Загрузил</th><th>Утвердил</th><th>Дата</th><th>Комментарий</th></tr></thead>
                            <tbody>
                                {[...doc.versions].reverse().map((v) => (
                                    <tr key={v.v}>
                                        <td className="mono">v{v.v}</td>
                                        <td>{v.fileName}</td>
                                        <td className="kb-muted">{v.uploadedBy}</td>
                                        <td className="kb-muted">{v.approvedBy}</td>
                                        <td className="kb-muted">{v.date}</td>
                                        <td className="kb-muted">{v.comment}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}

                    <div className="kb-aside-group-title" style={{ marginTop: 26 }}>Заметки к документу</div>
                    <div className="proj-notes-list">
                        {doc.notes.map((n) => (
                            <div key={n.id} className="proj-note-item">
                                <div className="proj-member-chip">{n.isAI ? '✦' : n.author.split(' ').map((w) => w[0]).join('')}</div>
                                <div style={{ flex: 1 }}>
                                    <div className="proj-activity-text">{n.text}</div>
                                    <div className="kb-muted proj-activity-when">{n.author} · {n.date}</div>
                                </div>
                                <span className="proj-note-delete" onClick={() => proj.deleteNote(doc.id, n.id)}>✕</span>
                            </div>
                        ))}
                    </div>
                    <div className="proj-note-input-row">
                        <input
                            className="field"
                            value={noteDraft}
                            onChange={(e) => setNoteDraft(e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Enter') handleAddNote(); }}
                            placeholder="Добавить заметку..."
                        />
                        <div className="proj-new-btn" onClick={handleAddNote}>Добавить</div>
                    </div>
                </div>
            </div>
        </main>
    );
}

export default DocumentView;
