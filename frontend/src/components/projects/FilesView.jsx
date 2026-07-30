import React from 'react';
import { SECTION_DEFS } from '../../hooks/useProjects';

// Дерево разделов/подразделов — только внутри FilesView, не переиспользуется
// больше нигде, поэтому не выделяю в отдельный файл.
function SectionTree({ proj, project, pDocs }) {
    return (
        <nav className="proj-file-tree">
            <div
                className={`proj-tree-row${proj.selectedSectionId === 'all' ? ' active' : ''}`}
                onClick={() => proj.selectSection('all')}
            >
                <span>Все разделы</span>
                <span className="mono kb-muted">{pDocs.length}</span>
            </div>
            {SECTION_DEFS.map((sec) => {
                const secDocs = pDocs.filter((d) => d.sectionId === sec.id);
                const expanded = proj.expandedSections.includes(sec.id);
                const subfolders = (project.subfolders[sec.id] || []).map((sf) => ({
                    ...sf, count: secDocs.filter((d) => d.subfolderId === sf.id).length,
                }));
                const active = proj.selectedSectionId === sec.id && proj.selectedSubfolderId === 'all';
                return (
                    <div key={sec.id}>
                        <div className={`proj-tree-row${active ? ' active' : ''}`}>
                            <span className={`proj-tree-caret${expanded ? ' open' : ''}`} onClick={() => proj.toggleExpandSection(sec.id)}>›</span>
                            <span onClick={() => proj.selectSection(sec.id)} style={{ flex: 1 }}>{sec.name}</span>
                            <span className="mono kb-muted">{secDocs.length}</span>
                        </div>
                        {expanded && (
                            <div className="proj-tree-children">
                                {subfolders.map((sf) => (
                                    <div
                                        key={sf.id}
                                        className={`proj-tree-row sub${proj.selectedSubfolderId === sf.id ? ' active' : ''}`}
                                        onClick={() => { proj.selectSection(sec.id); proj.selectSubfolder(sf.id); }}
                                    >
                                        <span style={{ flex: 1 }}>{sf.name}</span>
                                        <span className="mono kb-muted">{sf.count}</span>
                                    </div>
                                ))}
                                {proj.addingSubfolderSectionId === sec.id ? (
                                    <div className="proj-tree-row sub proj-tree-add-row">
                                        <input
                                            autoFocus
                                            className="field"
                                            value={proj.subfolderDraft}
                                            onChange={(e) => proj.setSubfolderDraft(e.target.value)}
                                            onKeyDown={(e) => { if (e.key === 'Enter') proj.confirmAddSubfolder(); if (e.key === 'Escape') proj.cancelAddSubfolder(); }}
                                            placeholder="Название подраздела"
                                        />
                                        <span className="proj-tree-add-confirm" onClick={proj.confirmAddSubfolder}>✓</span>
                                        <span className="proj-tree-add-cancel" onClick={proj.cancelAddSubfolder}>✕</span>
                                    </div>
                                ) : (
                                    <div className="proj-tree-row sub proj-tree-add-trigger" onClick={() => proj.startAddSubfolder(sec.id)}>
                                        + Добавить подраздел
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                );
            })}
        </nav>
    );
}

function FilesView({ proj, onUpload }) {
    const project = proj.projects.find((p) => p.id === proj.selectedProjectId);
    if (!project) return null;

    const pDocs = proj.projectDocs(project.id);
    let rows = proj.selectedSubfolderId !== 'all'
        ? pDocs.filter((d) => d.subfolderId === proj.selectedSubfolderId)
        : proj.selectedSectionId !== 'all'
            ? pDocs.filter((d) => d.sectionId === proj.selectedSectionId)
            : pDocs;

    const q = proj.filesQuery.trim().toLowerCase();
    if (q) rows = rows.filter((d) => (d.code + ' ' + d.name).toLowerCase().includes(q));

    return (
        <main className="proj-detail-shell">
            <aside className="proj-files-tree-aside">
                <div className="proj-back" onClick={proj.backToOverview}>← {project.name}</div>
                <SectionTree proj={proj} project={project} pDocs={pDocs} />
            </aside>

            <div className="proj-detail-center">
                <header className="proj-detail-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div className="kb-search-box" style={{ width: 260 }}>
                            <span>⌕</span>
                            <input className="field" value={proj.filesQuery} onChange={(e) => proj.setFilesQuery(e.target.value)} placeholder="Поиск по шифру/названию" />
                        </div>
                        <span className="kb-muted mono">{rows.length} документов</span>
                        <div className="proj-new-btn" style={{ marginLeft: 'auto' }} onClick={onUpload}>＋ Загрузить изменения</div>
                    </div>
                </header>

                <div className="proj-detail-body">
                    {pDocs.length === 0 ? (
                        <div className="proj-empty-state">В этом проекте пока нет документов.</div>
                    ) : rows.length === 0 ? (
                        <div className="proj-empty-state">Ничего не найдено по запросу «{proj.filesQuery}».</div>
                    ) : (
                        <table className="proj-files-table">
                            <thead>
                                <tr><th>Шифр</th><th>Наименование</th><th>Статус</th><th>Версия</th><th>Дата</th></tr>
                            </thead>
                            <tbody>
                                {rows.map((d) => {
                                    const badge = proj.docBadge(d);
                                    const lastVersion = d.versions[d.versions.length - 1];
                                    return (
                                        <tr key={d.id} onClick={() => proj.openDoc(d.id)}>
                                            <td className="mono">{d.code}</td>
                                            <td>{d.name}</td>
                                            <td><span className="proj-status-dot" style={{ background: badge.color }} /> {badge.label}</td>
                                            <td className="mono">{d.approvedVersion != null ? `v${d.approvedVersion}` : '—'}</td>
                                            <td className="kb-muted">{lastVersion?.date || '—'}</td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>
        </main>
    );
}

export default FilesView;
