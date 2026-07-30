import React from 'react';

function PdfPreviewOverlay({ proj }) {
    if (!proj.pdfOverlayOpen) return null;

    return (
        <div className="modal-overlay" onClick={proj.closePdf} onKeyDown={(e) => e.key === 'Escape' && proj.closePdf()}>
            <div className="modal-box proj-pdf-preview-box" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <span className="modal-title">{proj.pdfTitle}</span>
                    <button className="modal-close" onClick={proj.closePdf}>✕</button>
                </div>
                <div className="proj-pdf-preview-body">
                    <div className="kb-muted">Предпросмотр PDF (мок) — реальный рендер файла не подключён.</div>
                </div>
            </div>
        </div>
    );
}

export default PdfPreviewOverlay;
