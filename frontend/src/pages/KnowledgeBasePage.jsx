import React, { useEffect, useMemo, useRef } from 'react';
import DocumentCard from '../components/DocumentCard.jsx';
import { useKnowledgeBase } from '../hooks/useKnowledgeBase';

function KnowledgeBasePage({ api, showError }) {
    const kb = useKnowledgeBase(api, showError);
    const fileInputRef = useRef(null);

    useEffect(() => {
        kb.loadDocuments();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const isPersonal = kb.selectedCollection === 'personal';
    const lib = useMemo(() => kb.documents.filter((d) => !d.personal), [kb.documents]);
    const personal = useMemo(() => kb.documents.filter((d) => d.personal), [kb.documents]);

    const libCollections = useMemo(() => kb.collections.map((c) => ({
        ...c,
        count: c.id === 'all' ? lib.length : lib.filter((d) => d.collection === c.id).length,
    })), [kb.collections, lib]);

    const activeSet = useMemo(() => {
        let set = isPersonal
            ? personal
            : (kb.selectedCollection === 'all' ? lib : lib.filter((d) => d.collection === kb.selectedCollection));
        const q = kb.query.trim().toLowerCase();
        if (q) set = set.filter((d) => `${d.title} ${d.summary}`.toLowerCase().includes(q));
        return set;
    }, [isPersonal, personal, lib, kb.selectedCollection, kb.query]);

    const sum = (arr, key) => arr.reduce((a, d) => a + (d[key] || 0), 0);
    const pChunks = sum(personal, 'chunks');

    const selectedDoc = kb.documents.find((d) => d.id === kb.selectedDocId);

    const headTitle = isPersonal
        ? 'Моя база знаний'
        : (kb.collections.find((c) => c.id === kb.selectedCollection)?.label || 'Вся библиотека');
    const headSub = isPersonal
        ? 'Личные документы · разбивка на чанки и запись в векторную БД'
        : 'Документы команды · нажмите, чтобы увидеть краткое содержание и метрики индекса';

    const handlePickFile = () => fileInputRef.current?.click();
    const handleFileChange = (e) => {
        const file = e.target.files?.[0];
        e.target.value = '';
        if (file) kb.upload(file);
    };

    return (
        <>
            <aside className="kb-aside">
                <div className="kb-aside-header">
                    <div className="kb-aside-eyebrow">База знаний</div>
                    <div className="kb-aside-title">Инжиниринг</div>
                </div>

                <div className="kb-aside-body">
                    <div className="kb-aside-group-title">Библиотека</div>
                    {libCollections.map((c) => (
                        <div
                            key={c.id}
                            className={`kb-collection-item${kb.selectedCollection === c.id ? ' active' : ''}`}
                            onClick={() => kb.setSelectedCollection(c.id)}
                        >
                            <span className="kb-collection-icon">{c.icon}</span>
                            <span className="kb-collection-label">{c.label}</span>
                            <span className="mono kb-collection-count">{c.count}</span>
                        </div>
                    ))}

                    <div className="kb-aside-group-title">Личное</div>
                    <div
                        className={`kb-collection-item${isPersonal ? ' active' : ''}`}
                        onClick={() => kb.setSelectedCollection('personal')}
                    >
                        <span className="kb-collection-icon">★</span>
                        <span className="kb-collection-label">Моя база знаний</span>
                        <span className="mono kb-collection-count">{personal.length}</span>
                    </div>
                </div>

                <div className="kb-index-summary">
                    <div className="kb-index-summary-title">
                        <span className="kb-ok-dot" />
                        <span>Векторный индекс</span>
                    </div>
                    <div className="kb-index-row"><span>Документов</span><span className="mono">{kb.documents.length}</span></div>
                    <div className="kb-index-row"><span>Чанков текста</span><span className="mono">{sum(kb.documents, 'chunks')}</span></div>
                    <div className="kb-index-row"><span>Точек в БД</span><span className="mono kb-accent">{sum(kb.documents, 'chunks')}</span></div>
                </div>
            </aside>

            <main className="kb-main">
                <header className="kb-header">
                    <div>
                        <div className="kb-header-title">{headTitle}</div>
                        <div className="kb-header-sub">{headSub}</div>
                    </div>
                    <div className="kb-search">
                        <span>⌕</span>
                        <input
                            className="field"
                            value={kb.query}
                            onChange={(e) => kb.setQuery(e.target.value)}
                            placeholder="Поиск по документам"
                        />
                    </div>
                </header>

                <div className="kb-content">
                    {isPersonal && (
                        <div className="kb-upload-row">
                            <div className="kb-upload-zone" onClick={handlePickFile}>
                                <div className="kb-upload-icon">↑</div>
                                <div>
                                    <div className="kb-upload-title">Загрузить свой документ</div>
                                    <div className="kb-upload-sub">Перетащите файл или нажмите · PDF, MD, DOCX, TXT — до 25 МБ. Индексация запустится автоматически.</div>
                                </div>
                            </div>
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept=".pdf,.md,.docx,.txt,.markdown"
                                style={{ display: 'none' }}
                                onChange={handleFileChange}
                            />
                            <div className="kb-upload-stats">
                                <div className="kb-upload-stat"><div className="mono kb-upload-stat-value">{personal.length}</div><div className="kb-upload-stat-label">документов</div></div>
                                <div className="kb-upload-stat"><div className="mono kb-upload-stat-value">{pChunks}</div><div className="kb-upload-stat-label">чанков</div></div>
                                <div className="kb-upload-stat"><div className="mono kb-upload-stat-value kb-accent">{pChunks}</div><div className="kb-upload-stat-label">точек в БД</div></div>
                            </div>
                        </div>
                    )}

                    <div className="kb-grid">
                        {activeSet.map((d) => (
                            <DocumentCard key={d.id} doc={d} onOpen={kb.setSelectedDocId} />
                        ))}
                    </div>

                    {activeSet.length === 0 && kb.query.trim() && (
                        <div className="kb-empty">
                            <div className="kb-empty-icon">▤</div>
                            <div>Ничего не найдено по запросу «{kb.query}»</div>
                        </div>
                    )}
                </div>
            </main>

            {selectedDoc && (
                <>
                    <div className="kb-drawer-overlay" onClick={() => kb.setSelectedDocId(null)} />
                    <div className="kb-drawer">
                        <div className="kb-drawer-header">
                            <div className="kb-drawer-header-row">
                                <div className="mono kb-drawer-type">{selectedDoc.type_abbr}</div>
                                <div className="kb-drawer-title-wrap">
                                    <div className="kb-drawer-title">{selectedDoc.title}</div>
                                    <div className="kb-drawer-meta">{selectedDoc.type} · {selectedDoc.owner} · обновлён {selectedDoc.updated}</div>
                                </div>
                                <span className="kb-drawer-close" onClick={() => kb.setSelectedDocId(null)}>✕</span>
                            </div>
                            <div className="kb-drawer-pills">
                                <span className="kb-pill">
                                    <span className={`kb-status-dot${selectedDoc.status === 'processing' ? ' processing' : ''}`} />
                                    {selectedDoc.status === 'processing' ? 'Индексация…' : 'В индексе'}
                                </span>
                                <span className="kb-pill mono">{selectedDoc.size}</span>
                                <span className="kb-pill mono">{selectedDoc.pages} стр.</span>
                            </div>
                        </div>

                        <div className="kb-drawer-body">
                            <div className="kb-drawer-section-title kb-accent">Краткое по документу</div>
                            <div className="kb-drawer-summary">{selectedDoc.summary}</div>

                            <div className="kb-drawer-section-title">Векторизация</div>
                            <div className="kb-vec-grid">
                                <div className="kb-vec-cell"><div className="kb-vec-label">Размер чанка</div><div className="mono kb-vec-value">{selectedDoc.chunk_size} <span className="kb-muted">ток.</span></div></div>
                                <div className="kb-vec-cell"><div className="kb-vec-label">Перекрытие</div><div className="mono kb-vec-value">{selectedDoc.overlap} <span className="kb-muted">ток.</span></div></div>
                                <div className="kb-vec-cell"><div className="kb-vec-label">Чанков текста</div><div className="mono kb-vec-value">{selectedDoc.chunks}</div></div>
                                <div className="kb-vec-cell accent"><div className="kb-vec-label">Точек в векторной БД</div><div className="mono kb-vec-value">{selectedDoc.chunks}</div></div>
                                <div className="kb-vec-cell"><div className="kb-vec-label">Модель эмбеддингов</div><div className="mono kb-vec-value">{selectedDoc.model}</div></div>
                                <div className="kb-vec-cell"><div className="kb-vec-label">Размерность · метрика</div><div className="mono kb-vec-value">{selectedDoc.dim}d · {selectedDoc.metric}</div></div>
                            </div>

                            <div className="kb-drawer-section-header">
                                <span className="kb-drawer-section-title" style={{ margin: 0 }}>Краткое по разделам</span>
                                <span className="mono kb-muted">{selectedDoc.sections.length} разд.</span>
                            </div>
                            <div className="kb-sections">
                                {selectedDoc.sections.map((s, i) => (
                                    <div key={i} className="kb-section-item">
                                        <div className="kb-section-item-head">
                                            <span className="kb-section-item-title">{s.title}</span>
                                            <span className="mono kb-muted">▦ {s.chunks} · ◆ {s.chunks}</span>
                                        </div>
                                        <div className="kb-section-item-summary">{s.summary}</div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="kb-drawer-footer">
                            <div className="kb-drawer-ask" onClick={() => kb.setSelectedDocId(null)}>Спросить ассистента →</div>
                            {selectedDoc.personal && (
                                <div className="kb-drawer-reindex" title="Переиндексировать" onClick={() => kb.reindex(selectedDoc.id)}>↻</div>
                            )}
                        </div>
                    </div>
                </>
            )}
        </>
    );
}

export default KnowledgeBasePage;
