import React from 'react';
import { Rnd } from 'react-rnd';

// Независим от DocumentReader — открывается и с карточки в библиотеке (без захода
// в саму читалку), и из читалки. bounds="window" вместо "parent": рендерится на уровне
// страницы (KnowledgeBasePage), а не внутри .kb-reader, так что своего position:fixed
// родителя-«системы координат» может не быть.
function SourceViewerWindow({ doc, onClose }) {
    if (!doc?.file_url) return null;

    return (
        <Rnd
            className="kb-source-window"
            default={{ x: 60, y: 50, width: 820, height: 620 }}
            minWidth={420}
            minHeight={320}
            bounds="window"
            dragHandleClassName="kb-source-viewer-head"
        >
            <div className="kb-source-viewer">
                <div className="kb-source-viewer-head">
                    <span className="kb-source-viewer-title">{doc.title}</span>
                    <a href={doc.file_url} target="_blank" rel="noopener noreferrer" className="kb-source-viewer-link">Открыть в новой вкладке ↗</a>
                    <span className="kb-source-viewer-close" title="Закрыть" onClick={onClose}>✕</span>
                </div>
                <iframe src={doc.file_url} className="kb-source-viewer-frame" title={`Исходник: ${doc.title}`} />
            </div>
        </Rnd>
    );
}

export default SourceViewerWindow;
