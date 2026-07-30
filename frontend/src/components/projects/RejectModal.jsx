import React from 'react';

function RejectModal({ proj }) {
    if (!proj.rejectModalOpen) return null;

    return (
        <div className="modal-overlay" onClick={proj.closeReject} onKeyDown={(e) => e.key === 'Escape' && proj.closeReject()}>
            <div className="modal-box" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <span className="modal-title">Отклонить пакет</span>
                    <button className="modal-close" onClick={proj.closeReject}>✕</button>
                </div>
                <div className="modal-body">
                    <label className="modal-label">Причина отклонения</label>
                    <textarea
                        className="field"
                        style={{ minHeight: 90, resize: 'vertical' }}
                        placeholder="Что нужно исправить..."
                        value={proj.rejectComment}
                        onChange={(e) => proj.setRejectComment(e.target.value)}
                        autoFocus
                    />
                    <div className="modal-actions">
                        <button className="modal-btn-cancel" onClick={proj.closeReject}>Отмена</button>
                        <button className="modal-btn-save" onClick={proj.confirmReject}>Отклонить</button>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default RejectModal;
