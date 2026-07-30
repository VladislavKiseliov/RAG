import React from 'react';

function UploadChangesetModal({ proj }) {
    if (!proj.uploadModalOpen) return null;
    const project = proj.projects.find((p) => p.id === proj.selectedProjectId);
    const pDocs = project ? proj.projectDocs(project.id) : [];

    return (
        <div className="modal-overlay" onClick={proj.closeUpload} onKeyDown={(e) => e.key === 'Escape' && proj.closeUpload()}>
            <div className="modal-box" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <span className="modal-title">Загрузить пакет изменений</span>
                    <button className="modal-close" onClick={proj.closeUpload}>✕</button>
                </div>

                <div className="modal-body">
                    <div className="proj-upload-items">
                        {proj.uploadItems.map((it) => (
                            <div key={it.id} className="proj-upload-item">
                                <span className="mono" style={{ flex: 1 }}>{it.fileName}</span>
                                <select className="field" value={it.mode} onChange={(e) => proj.setUploadItemMode(it.id, e.target.value)} style={{ width: 140 }}>
                                    <option value="new">Новый документ</option>
                                    <option value="replace">Замена версии</option>
                                </select>
                                {it.mode === 'replace' ? (
                                    <select className="field" value={it.docId} onChange={(e) => proj.setUploadItemDoc(it.id, e.target.value)} style={{ flex: 1 }}>
                                        <option value="">Выберите документ...</option>
                                        {pDocs.map((d) => <option key={d.id} value={d.id}>{d.code} — {d.name}</option>)}
                                    </select>
                                ) : (
                                    <input className="field" placeholder="Шифр (необязательно)" value={it.newCode} onChange={(e) => proj.setUploadItemCode(it.id, e.target.value)} style={{ flex: 1 }} />
                                )}
                                <span className="proj-note-delete" onClick={() => proj.removeUploadItem(it.id)}>✕</span>
                            </div>
                        ))}
                    </div>

                    <div className="proj-upload-add-btn" onClick={proj.addUploadFile}>＋ Добавить файл</div>

                    <textarea
                        className="field"
                        style={{ marginTop: 12, minHeight: 70, resize: 'vertical' }}
                        placeholder="Комментарий к пакету изменений"
                        value={proj.uploadComment}
                        onChange={(e) => proj.setUploadComment(e.target.value)}
                    />

                    <div className="modal-actions">
                        <button className="modal-btn-cancel" onClick={proj.closeUpload}>Отмена</button>
                        <button className="modal-btn-save" onClick={proj.submitUpload}>Отправить на утверждение</button>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default UploadChangesetModal;
