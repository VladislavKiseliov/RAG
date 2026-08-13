import React from 'react';

function DocumentCard({ doc, onOpen, onOpenSource }) {
    const isProcessing = doc.status === 'processing';

    return (
        <div className="kb-card" onClick={() => onOpen(doc.id)}>
            <div className="kb-card-top">
                <div className="kb-card-type mono">{doc.type_abbr}</div>
                <div className="kb-card-status">
                    <span className={`kb-status-dot${isProcessing ? ' processing' : ''}`} />
                    <span>{isProcessing ? 'Индексация…' : 'В индексе'}</span>
                </div>
                <div
                    className="kb-card-source-btn"
                    title="Открыть исходный файл"
                    onClick={(e) => { e.stopPropagation(); onOpenSource(doc.id); }}
                >
                    ⤢
                </div>
            </div>
            <div className="kb-card-title">{doc.title}</div>
            <div className="kb-card-summary clamp3">{doc.summary}</div>
            <div className="kb-card-footer">
                <span className="mono kb-card-chunks">▦ {doc.chunks} <span className="kb-muted">чанк.</span></span>
                <span className="mono kb-card-points">◆ {doc.chunks} <span className="kb-muted">точек</span></span>
                <span className="mono kb-card-size">{doc.size}</span>
            </div>
        </div>
    );
}

export default DocumentCard;
