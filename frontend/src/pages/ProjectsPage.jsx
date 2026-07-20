import React, { useEffect, useRef } from 'react';
import ProjectCard from '../components/ProjectCard.jsx';
import { useProjects } from '../hooks/useProjects';

function ProjectsPage({ onOpenMessenger, onOpenKnowledge }) {
    const proj = useProjects();
    const fileInputRef = useRef(null);

    useEffect(() => {
        proj.loadProjects();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const statActive = proj.projects.filter((p) => p.kind === 'active').length;
    const statTasks = proj.projects.reduce((a, p) => a + p.tasks.filter((t) => !t.done).length, 0);
    const statWeek = proj.projects.reduce((a, p) => a + p.activity.length, 0);

    if (proj.view === 'list') {
        return (
            <main className="proj-main">
                <header className="proj-header">
                    <div className="proj-header-row">
                        <div>
                            <div className="proj-eyebrow">Рабочее пространство</div>
                            <div className="proj-title">Проекты</div>
                        </div>
                        <div className="proj-new-btn"><span>＋</span> Новый проект</div>
                    </div>

                    <div className="proj-stats-strip">
                        <div className="proj-stat-card"><div className="mono proj-stat-value accent">{proj.projects.length}</div><div className="proj-stat-label">проектов на вас</div></div>
                        <div className="proj-stat-card"><div className="mono proj-stat-value">{statActive}</div><div className="proj-stat-label">в активной работе</div></div>
                        <div className="proj-stat-card"><div className="mono proj-stat-value">{statTasks}</div><div className="proj-stat-label">открытых задач</div></div>
                        <div className="proj-stat-card"><div className="mono proj-stat-value ok">+{statWeek}</div><div className="proj-stat-label">обновлений за неделю</div></div>
                    </div>
                </header>

                <div className="proj-content">
                    <div className="kb-aside-group-title">Ваши проекты</div>
                    <div className="proj-grid">
                        {proj.projects.map((p) => (
                            <ProjectCard key={p.id} project={p} onOpen={proj.openProject} />
                        ))}
                    </div>
                </div>
            </main>
        );
    }

    const project = proj.projects.find((p) => p.id === proj.selectedId);
    if (!project) return null;

    const done = project.tasks.filter((t) => t.done).length;
    const progress = Math.round((done / project.tasks.length) * 100);
    const statusClass = { active: 'ok', review: 'accent', plan: 'muted' }[project.kind];

    const handleAddFile = () => fileInputRef.current?.click();
    const handleFileChange = (e) => {
        const files = Array.from(e.target.files || []);
        e.target.value = '';
        if (files.length) proj.addFile(project.id, files);
    };

    return (
        <main className="proj-detail-shell">
            <div className="proj-detail-center">
                <header className="proj-detail-header">
                    <div className="proj-back" onClick={proj.back}>← Все проекты</div>
                    <div className="proj-detail-title-row">
                        <div className="proj-card-glyph large">{project.glyph}</div>
                        <div>
                            <div className="proj-detail-name">{project.name}</div>
                            <div className="proj-detail-meta">
                                <span className={`proj-status-dot ${statusClass}`} />
                                <span>{project.status} · {project.lead} · {project.deadline}</span>
                            </div>
                        </div>
                        <div className="proj-chat-link" onClick={onOpenMessenger}>
                            <span className="kb-accent">✦</span> Чат проекта
                        </div>
                    </div>
                </header>

                <div className="proj-detail-body">
                    <div className="proj-detail-desc">{project.desc}</div>

                    <div className="proj-drawer-section-header">
                        <span className="kb-drawer-section-title" style={{ margin: 0 }}>Задачи</span>
                        <span className="mono">{done} из {project.tasks.length}</span>
                    </div>
                    <div className="proj-progress-track wide"><div className="proj-progress-fill" style={{ width: `${progress}%` }} /></div>
                    <div className="proj-task-list">
                        {project.tasks.map((t, i) => (
                            <div key={i} className="proj-task-item" onClick={() => proj.toggleTask(project.id, i)}>
                                <span className={`proj-task-box${t.done ? ' done' : ''}`}>{t.done ? '✓' : ''}</span>
                                <span className={`proj-task-text${t.done ? ' done' : ''}`}>{t.t}</span>
                                <span className="mono kb-muted proj-task-assignee">{t.assignee}</span>
                            </div>
                        ))}
                    </div>

                    <div className="kb-aside-group-title">Активность</div>
                    <div className="proj-activity-list">
                        {project.activity.map((a, i) => (
                            <div key={i} className="proj-activity-item">
                                <div className="proj-member-chip">{a.who}</div>
                                <div>
                                    <div className="proj-activity-text">{a.text}</div>
                                    <div className="kb-muted proj-activity-when">{a.when}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            <aside className="proj-right-panel">
                <div className="proj-panel-section-header">
                    <span className="kb-aside-group-title" style={{ padding: 0 }}>Файлы проекта · {project.files.length}</span>
                    <span className="proj-add-file" title="Добавить файл" onClick={handleAddFile}>＋</span>
                    <input ref={fileInputRef} type="file" multiple style={{ display: 'none' }} onChange={handleFileChange} />
                </div>
                <div className="proj-file-list">
                    {project.files.map((f, i) => (
                        <div key={i} className="proj-file-item">
                            <div className="mono proj-file-ext">{f.ext}</div>
                            <div className="proj-file-info">
                                <div className="proj-file-name">{f.name}</div>
                                <div className="kb-muted proj-file-meta">{f.size} · {f.by} · {f.when}</div>
                            </div>
                            {f.fresh && <span className="proj-file-dot">●</span>}
                        </div>
                    ))}
                </div>

                <div className="proj-panel-section-header bordered">
                    <span className="kb-aside-group-title" style={{ padding: 0 }}>Из базы знаний</span>
                    <span className="proj-doc-open-all" onClick={onOpenKnowledge}>Открыть →</span>
                </div>
                <div className="proj-doc-list">
                    {project.docs.map((d, i) => (
                        <div key={i} className="proj-doc-item" onClick={onOpenKnowledge}>
                            <span className="kb-accent">▤</span>
                            <span className="proj-doc-title">{d.title}</span>
                            <span className="mono kb-muted proj-doc-points">◆ {d.points}</span>
                        </div>
                    ))}
                </div>

                <div className="proj-panel-section-header bordered">
                    <span className="kb-aside-group-title" style={{ padding: 0 }}>Участники · {project.members.length}</span>
                </div>
                <div className="proj-member-list">
                    {project.members.map((m, i) => (
                        <div key={i} className="proj-member-row">
                            <div className="proj-member-chip large">{m.init}</div>
                            <div>
                                <div className="proj-member-name">{m.name}</div>
                                <div className="kb-muted proj-member-role">{m.role}</div>
                            </div>
                        </div>
                    ))}
                </div>
            </aside>
        </main>
    );
}

export default ProjectsPage;
