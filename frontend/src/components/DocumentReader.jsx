import React, { useState } from 'react';
import { Rnd } from 'react-rnd';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import AssistantChatPanel from './AssistantChatPanel.jsx';

const fmt = (v) => (v === null || v === undefined ? '—' : v);

// Бэкенд оставляет маркер [→ Таблица N] в тексте главы вместо того чтобы его вырезать —
// разбиваем текст по маркерам, чтобы вставить карточку таблицы на её реальном месте,
// а не одним списком в конце.
const TABLE_LINK_RE = /\[→\s*Таблица\s+(\d+)\]\([^)]*\)/g;

const splitChapterText = (text) => {
    const segments = [];
    let lastIndex = 0;
    let match;
    TABLE_LINK_RE.lastIndex = 0;
    while ((match = TABLE_LINK_RE.exec(text)) !== null) {
        const before = text.slice(lastIndex, match.index).trim();
        if (before) segments.push({ type: 'text', content: before });
        segments.push({ type: 'table', index: Number(match[1]) });
        lastIndex = TABLE_LINK_RE.lastIndex;
    }
    const rest = text.slice(lastIndex).trim();
    if (rest) segments.push({ type: 'text', content: rest });
    return segments;
};

function DocumentReader({
    doc, chapterIdx, contentMode, chapterContent, chapterContentLoading,
    onOpenChapter, onBackToOverview, onSetMode, onClose, onReindex,
    sourceViewerOpen, onOpenSource, onCloseSource,
}) {
    const chapter = chapterIdx !== null ? doc.sections[chapterIdx] : null;
    const isProcessing = doc.status === 'processing';
    const chapterTables = chapterContent?.tables ?? [];
    const [chatOpen, setChatOpen] = useState(false);

    return (
        <div className="kb-reader">
            <header className="kb-reader-topbar">
                <div className="kb-reader-badge mono">{doc.type_abbr}</div>
                <div className="kb-reader-title-wrap">
                    <div className="kb-reader-title">{doc.title}</div>
                    <div className="kb-reader-meta">{doc.type} · {doc.owner} · обновлён {doc.updated}</div>
                </div>
                {doc.file_url && (
                    <div className="kb-reader-source-btn" title="Открыть исходный файл на этой странице" onClick={onOpenSource}>⤢ Открыть исходник</div>
                )}
                <div className="kb-reader-ask" onClick={() => setChatOpen(true)}>Спросить ассистента →</div>
                {onReindex && (
                    <div className="kb-reader-icon-btn" title="Переиндексировать" onClick={onReindex}>↻</div>
                )}
                <div className="kb-reader-icon-btn" title="Закрыть" onClick={onClose}>✕</div>
            </header>

            {sourceViewerOpen && doc.file_url && (
                <Rnd
                    className="kb-source-window"
                    default={{ x: 60, y: 50, width: 820, height: 620 }}
                    bounds="parent"
                    dragHandleClassName="kb-source-viewer-head"
                    enableResizing={false}
                >
                    <div className="kb-source-viewer">
                        <div className="kb-source-viewer-head">
                            <span className="kb-source-viewer-title">{doc.title}</span>
                            <a href={doc.file_url} target="_blank" rel="noopener noreferrer" className="kb-source-viewer-link">Открыть в новой вкладке ↗</a>
                            <span className="kb-source-viewer-close" title="Закрыть" onClick={onCloseSource}>✕</span>
                        </div>
                        <iframe src={doc.file_url} className="kb-source-viewer-frame" title={`Исходник: ${doc.title}`} />
                    </div>
                </Rnd>
            )}

            {chatOpen && (
                <AssistantChatPanel title={doc.title} onClose={() => setChatOpen(false)} />
            )}

            <div className={`kb-reader-body${chatOpen ? ' chat-open' : ''}`}>
                <aside className="kb-reader-outline">
                    <div className="kb-reader-chips">
                        <span className="kb-pill">
                            <span className={`kb-status-dot${isProcessing ? ' processing' : ''}`} />
                            {isProcessing ? 'Индексация…' : 'В индексе'}
                        </span>
                        <span className="kb-pill mono">{doc.size} · {fmt(doc.pages)} стр.</span>
                    </div>

                    <div className="kb-drawer-section-title">Характеристики</div>
                    <div className="kb-vec-grid">
                        <div className="kb-vec-cell"><div className="kb-vec-label">Объём</div><div className="mono kb-vec-value">{fmt(doc.pages)} <span className="kb-vec-unit">стр.</span></div></div>
                        <div className="kb-vec-cell"><div className="kb-vec-label">Структура</div><div className="mono kb-vec-value">{fmt(doc.chapters_count)} <span className="kb-vec-unit">глав</span></div></div>
                        <div className="kb-vec-cell"><div className="kb-vec-label">Чанков (фрагментов)</div><div className="mono kb-vec-value">{fmt(doc.chunks)}</div></div>
                        <div className="kb-vec-cell"><div className="kb-vec-label">Таблиц и схем</div><div className="mono kb-vec-value">{fmt(doc.tables_count)} <span className="kb-vec-unit">табл.</span></div></div>
                    </div>

                    <div className="kb-drawer-section-title">Оглавление</div>
                    <nav className="kb-reader-toc">
                        <div
                            className={`kb-reader-toc-item${chapterIdx === null ? ' active' : ''}`}
                            onClick={onBackToOverview}
                        >
                            ▤ Обзор документа
                        </div>
                        {doc.sections.map((s, i) => (
                            <div
                                key={i}
                                className={`kb-reader-toc-item${chapterIdx === i ? ' active' : ''}`}
                                onClick={() => onOpenChapter(i)}
                            >
                                <span className="kb-reader-toc-title">{s.title}</span>
                                <span className="count mono kb-muted">{fmt(s.chunks)}</span>
                            </div>
                        ))}
                    </nav>
                </aside>

                <main className="kb-reader-content">
                    <div className="kb-reader-content-inner">
                        <div className="kb-reader-content-head">
                            <h2>{chapter ? chapter.title : 'Обзор документа'}</h2>
                            {chapter && (
                                <span className="mono kb-muted">▦ {fmt(chapter.chunks)} чанк. · ◆ {fmt(chapter.chunks)} точ.</span>
                            )}
                        </div>

                        {chapter && (
                            <div className="kb-reader-mode-tabs">
                                <button className={contentMode === 'summary' ? 'active' : ''} onClick={() => onSetMode('summary')}>Краткое</button>
                                <button className={contentMode === 'full' ? 'active' : ''} onClick={() => onSetMode('full')}>Весь текст</button>
                            </div>
                        )}

                        {!chapter && (
                            <div className="kb-reader-summary-card message-markdown">
                                <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{doc.summary}</ReactMarkdown>
                            </div>
                        )}
                        {chapter && contentMode === 'summary' && (
                            <div className="kb-reader-summary-card message-markdown">
                                <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{chapter.summary}</ReactMarkdown>
                            </div>
                        )}

                        {chapter && contentMode === 'full' && chapterContentLoading && (
                            <div className="kb-reader-summary-card kb-muted">Загрузка текста главы…</div>
                        )}

                        {chapter && contentMode === 'full' && !chapterContentLoading && (
                            <div>
                                {splitChapterText(chapterContent?.text || '').map((seg, i) => {
                                    if (seg.type === 'text') {
                                        return (
                                            <div key={i} className="kb-reader-full-text message-markdown">
                                                <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{seg.content}</ReactMarkdown>
                                            </div>
                                        );
                                    }
                                    const tb = chapterTables.find((t) => t.table_index === seg.index);
                                    if (!tb) return null;
                                    return (
                                        <div key={i} className="kb-reader-table-card">
                                            <div className="kb-reader-table-head">▦ {tb.name}</div>
                                            <table>
                                                <thead><tr>{tb.cols.map((c, ci) => <th key={ci}>{c}</th>)}</tr></thead>
                                                <tbody>
                                                    {tb.rows.map((r, ri) => (
                                                        <tr key={ri}>{r.map((cell, ci) => <td key={ci}>{cell}</td>)}</tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </main>
            </div>
        </div>
    );
}

export default DocumentReader;