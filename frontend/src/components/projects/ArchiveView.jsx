import React from 'react';
import { SECTION_DEFS } from '../../hooks/useProjects';

const STATUS_LABEL = { approved: 'Утверждён', rejected: 'Отклонён' };

function ArchiveView({ proj }) {
    const project = proj.projects.find((p) => p.id === proj.selectedProjectId);
    if (!project) return null;

    const history = proj.projectChangesets(project.id).filter((c) => c.status === 'approved' || c.status === 'rejected');
    const withSection = history.map((cs) => {
        const firstDoc = cs.items[0]?.docId ? proj.docs.find((d) => d.id === cs.items[0].docId) : null;
        return { cs, sectionId: firstDoc?.sectionId || null };
    });
    const rows = proj.archiveSection === 'all' ? withSection : withSection.filter((r) => r.sectionId === proj.archiveSection);

    return (
        <main className="proj-detail-shell">
            <div className="proj-detail-center">
                <header className="proj-detail-header">
                    <div className="proj-back" onClick={proj.backToOverview}>← {project.name}</div>
                    <div className="proj-detail-title-row"><div className="proj-detail-name">Архив версий</div></div>
                </header>

                <div className="proj-detail-body">
                    <div className="proj-archive-filters">
                        <span className={`proj-archive-filter${proj.archiveSection === 'all' ? ' active' : ''}`} onClick={() => proj.setArchiveSection('all')}>Все разделы</span>
                        {SECTION_DEFS.map((sec) => (
                            <span key={sec.id} className={`proj-archive-filter${proj.archiveSection === sec.id ? ' active' : ''}`} onClick={() => proj.setArchiveSection(sec.id)}>
                                {sec.name}
                            </span>
                        ))}
                    </div>

                    {rows.length === 0 ? (
                        <div className="proj-empty-state">В этом разделе пока нет истории.</div>
                    ) : (
                        <table className="proj-files-table" style={{ marginTop: 16 }}>
                            <thead><tr><th>Пакет</th><th>Автор</th><th>Статус</th><th>Дата</th></tr></thead>
                            <tbody>
                                {rows.map(({ cs }) => (
                                    <tr key={cs.id} onClick={() => { const first = cs.items[0]; if (first?.docId) proj.openDoc(first.docId); }}>
                                        <td>{cs.comment}</td>
                                        <td className="kb-muted">{cs.author}</td>
                                        <td>
                                            <span className="proj-status-dot" style={{ background: cs.status === 'approved' ? 'var(--ok)' : '#d65f5f' }} />
                                            {STATUS_LABEL[cs.status]}
                                        </td>
                                        <td className="kb-muted">{cs.date}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>
        </main>
    );
}

export default ArchiveView;
