import React, { useEffect, useMemo, useRef } from 'react';
import DocumentCard from '../components/DocumentCard.jsx';
import DocumentReader from '../components/DocumentReader.jsx';
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
                            <DocumentCard key={d.id} doc={d} onOpen={kb.openDoc} />
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
                <DocumentReader
                    doc={selectedDoc}
                    chapterIdx={kb.chapterIdx}
                    contentMode={kb.contentMode}
                    chapterContent={kb.chapterContent}
                    chapterContentLoading={kb.chapterContentLoading}
                    onOpenChapter={kb.openChapter}
                    onBackToOverview={kb.backToOverview}
                    onSetMode={kb.setContentMode}
                    onClose={kb.closeDoc}
                    onReindex={selectedDoc.personal ? () => kb.reindex(selectedDoc.id) : undefined}
                />
            )}
        </>
    );
}

export default KnowledgeBasePage;
