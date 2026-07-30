import React from 'react';

function NewProjectModal({ proj }) {
    if (!proj.newProjectModalOpen) return null;

    return (
        <div className="modal-overlay" onClick={proj.closeNewProject} onKeyDown={(e) => e.key === 'Escape' && proj.closeNewProject()}>
            <div className="modal-box" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <span className="modal-title">Новый проект</span>
                    <button className="modal-close" onClick={proj.closeNewProject}>✕</button>
                </div>
                <div className="modal-body">
                    <label className="modal-label">Название проекта</label>
                    <input
                        className="field"
                        value={proj.newProjectName}
                        onChange={(e) => proj.setNewProjectName(e.target.value)}
                        placeholder="Например, БПГ-102"
                        autoFocus
                    />
                    <label className="modal-label" style={{ marginTop: 12 }}>Тип проекта</label>
                    <select className="field" value={proj.newProjectType} onChange={(e) => proj.setNewProjectType(e.target.value)}>
                        {proj.projectTypeOptions.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
                    </select>
                    <div className="modal-actions">
                        <button className="modal-btn-cancel" onClick={proj.closeNewProject}>Отмена</button>
                        <button className="modal-btn-save" onClick={proj.submitNewProject}>Создать</button>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default NewProjectModal;
