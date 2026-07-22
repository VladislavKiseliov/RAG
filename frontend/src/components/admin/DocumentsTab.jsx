import React, { useRef, useState } from 'react';

function DocumentsTab({ admin }) {
    const [draftTitle, setDraftTitle] = useState('');
    const fileInputRef = useRef(null);
    const isPersonal = admin.docScope === 'personal';
    const source = isPersonal ? admin.personalDocuments : admin.documents;
    const byUser = isPersonal && admin.personalUserId
        ? source.filter((d) => d.ownerId === admin.personalUserId)
        : source;
    const q = admin.docQuery.trim().toLowerCase();
    const rows = q ? byUser.filter((d) => d.title.toLowerCase().includes(q)) : byUser;

    const pickerQuery = admin.userPickerQuery.trim().toLowerCase();
    const pickerUsers = admin.users.filter((u) => u.name.toLowerCase().includes(pickerQuery));
    const selectedUser = admin.users.find((u) => u.id === admin.personalUserId);
    const totalPersonalDocs = admin.personalDocuments.length;

    const startEdit = (d) => { admin.setEditingDocId(d.id); setDraftTitle(d.title); };
    const commitEdit = (docId) => { admin.renameDocumentLocal(docId, draftTitle); admin.setEditingDocId(null); };

    const handlePickFile = () => fileInputRef.current?.click();
    const handleFileChange = (e) => {
        const files = Array.from(e.target.files || []);
        e.target.value = '';
        if (files.length) admin.uploadDocuments(files);
    };

    return (
        <div>
            <div className="adm-segment">
                <button className={!isPersonal ? 'active' : ''} onClick={() => admin.setDocScope('shared')}>Общая база знаний</button>
                <button className={isPersonal ? 'active' : ''} onClick={() => admin.setDocScope('personal')}>Личные базы пользователей</button>
            </div>

            <div className="adm-toolbar">
                {isPersonal && (
                    <div className="adm-user-picker">
                        <button className="adm-user-picker-btn" onClick={() => admin.setUserPickerOpen((v) => !v)}>
                            {selectedUser ? `${selectedUser.name} · ${byUser.length}` : `Все пользователи · ${totalPersonalDocs}`} ▾
                        </button>
                        {admin.userPickerOpen && (
                            <div className="adm-user-picker-panel">
                                <input
                                    className="field"
                                    placeholder="Найти пользователя…"
                                    value={admin.userPickerQuery}
                                    onChange={(e) => admin.setUserPickerQuery(e.target.value)}
                                    autoFocus
                                />
                                <div className="adm-user-picker-list">
                                    <div className="adm-user-picker-item" onClick={() => { admin.setPersonalUserId(null); admin.setUserPickerOpen(false); }}>Все пользователи</div>
                                    {pickerUsers.map((u) => (
                                        <div key={u.id} className="adm-user-picker-item" onClick={() => { admin.setPersonalUserId(u.id); admin.setUserPickerOpen(false); }}>
                                            <span className="adm-avatar">{(u.name?.[0] || '?').toUpperCase()}</span>
                                            <span>{u.name}</span>
                                            <span className="count mono kb-muted">{u.docsCount ?? '—'}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}
                <input
                    className="field adm-doc-search"
                    placeholder="Поиск по документам"
                    value={admin.docQuery}
                    onChange={(e) => admin.setDocQuery(e.target.value)}
                />
                {!isPersonal && (
                    <>
                        <button className="adm-upload-btn" onClick={handlePickFile} disabled={admin.uploading}>
                            {admin.uploading ? 'Загрузка…' : '↑ Загрузить документы'}
                        </button>
                        <input
                            ref={fileInputRef}
                            type="file"
                            multiple
                            accept=".pdf,.md,.docx,.txt,.markdown"
                            style={{ display: 'none' }}
                            onChange={handleFileChange}
                        />
                    </>
                )}
            </div>

            <table className="adm-table">
                <thead>
                    <tr><th>Документ</th><th>Владелец</th><th>Чанков</th><th>Точек</th><th>Размер</th><th>Статус</th><th /></tr>
                </thead>
                <tbody>
                    {rows.map((d) => (
                        <tr key={d.id}>
                            <td>
                                {admin.editingDocId === d.id ? (
                                    <input
                                        autoFocus
                                        className="field"
                                        value={draftTitle}
                                        onChange={(e) => setDraftTitle(e.target.value)}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter') commitEdit(d.id);
                                            if (e.key === 'Escape') admin.setEditingDocId(null);
                                        }}
                                        onBlur={() => admin.setEditingDocId(null)}
                                    />
                                ) : (
                                    <span className="adm-doc-title">
                                        {d.title}
                                        <span className="adm-edit-icon" onClick={() => startEdit(d)}>✎</span>
                                    </span>
                                )}
                            </td>
                            <td>{d.owner}</td>
                            <td className="mono">{d.chunks ?? '—'}</td>
                            <td className="mono">{d.points ?? '—'}</td>
                            <td className="mono">{d.size}</td>
                            <td>
                                <span className={`status-pill ${d.state === 'indexed' ? 'online' : 'degraded'}`}>
                                    <span className="dot" />{d.state === 'indexed' ? 'В индексе' : 'Индексация'}
                                </span>
                            </td>
                            <td className="adm-row-actions">
                                {!isPersonal && <span title="Переиндексировать" onClick={() => admin.reindexDocument(d.id)}>↻</span>}
                                {!isPersonal && <span title="Пересобрать саммари" onClick={() => admin.summarizeDocument(d.id)}>✎</span>}
                                {!isPersonal && <span title="Удалить" onClick={() => admin.deleteDocument(d.id)}>🗑</span>}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
            {rows.length === 0 && <div className="kb-empty">Документы не найдены</div>}
        </div>
    );
}

export default DocumentsTab;