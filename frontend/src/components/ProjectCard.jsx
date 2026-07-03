import React from 'react';

const STATUS_CLASS = { active: 'ok', review: 'accent', plan: 'muted' };

function ProjectCard({ project, onOpen }) {
    const done = project.tasks.filter((t) => t.done).length;
    const progress = Math.round((done / project.tasks.length) * 100);

    return (
        <div className="proj-card" onClick={() => onOpen(project.id)}>
            <div className="proj-card-top">
                <div className="proj-card-glyph">{project.glyph}</div>
                <div className="proj-card-name-wrap">
                    <div className="proj-card-name">{project.name}</div>
                    <div className="proj-card-status">
                        <span className={`proj-status-dot ${STATUS_CLASS[project.kind]}`} />
                        <span>{project.status}</span>
                    </div>
                </div>
            </div>
            <div className="proj-card-desc clamp2">{project.desc}</div>
            <div className="proj-card-progress">
                <div className="proj-card-progress-row">
                    <span className="kb-muted">Задачи</span>
                    <span className="mono">{done}/{project.tasks.length}</span>
                </div>
                <div className="proj-progress-track">
                    <div className="proj-progress-fill" style={{ width: `${progress}%` }} />
                </div>
            </div>
            <div className="proj-card-footer">
                <div className="proj-card-members">
                    {project.members.map((m, i) => (
                        <div key={i} className="proj-member-chip">{m.init}</div>
                    ))}
                </div>
                <span className="mono kb-muted">▤ {project.files.length}</span>
                <span className="mono kb-muted proj-card-updated">{project.updated}</span>
            </div>
        </div>
    );
}

export default ProjectCard;
