import React, { useState } from 'react';
import { useProjects } from '../hooks/useProjects';
import AssistantChatPanel from '../components/AssistantChatPanel.jsx';
import ListView from '../components/projects/ListView.jsx';
import OverviewView from '../components/projects/OverviewView.jsx';
import FilesView from '../components/projects/FilesView.jsx';
import DocumentView from '../components/projects/DocumentView.jsx';
import QueueView from '../components/projects/QueueView.jsx';
import ArchiveView from '../components/projects/ArchiveView.jsx';
import UploadChangesetModal from '../components/projects/UploadChangesetModal.jsx';
import RejectModal from '../components/projects/RejectModal.jsx';
import NewProjectModal from '../components/projects/NewProjectModal.jsx';
import PdfPreviewOverlay from '../components/projects/PdfPreviewOverlay.jsx';
import MockBadge from '../components/MockBadge.jsx';

function ProjectsPage() {
    const proj = useProjects();
    // Чат привязан к ключу (проект/документ, для которого его открыли) —
    // переход на другой проект/документ меняет currentKey, и панель закрывается
    // сама (производное состояние), без эффекта с setState.
    const [chatOpenKey, setChatOpenKey] = useState(null);

    const project = proj.projects.find((p) => p.id === proj.selectedProjectId);
    const doc = proj.docs.find((d) => d.id === proj.selectedDocId);
    const chatTitle = proj.view === 'document' && doc ? doc.name : project ? project.name : 'Проекты';

    const currentKey = proj.view === 'document' ? `doc:${proj.selectedDocId}` : `proj:${proj.selectedProjectId}`;
    const chatOpen = chatOpenKey !== null && chatOpenKey === currentKey;
    const openChat = () => setChatOpenKey(currentKey);
    const closeChat = () => setChatOpenKey(null);

    return (
        <div className={`proj-page-shell${chatOpen ? ' chat-open' : ''}`}>
            <div className="proj-role-bar">
                <MockBadge title="Проекты целиком на демо-данных — нет ни одного реального API-вызова" />
                <span className="kb-muted">Роль (демо):</span>
                <div className="proj-role-switch">
                    <span className={proj.role === 'manager' ? 'active' : ''} onClick={() => proj.setRole('manager')}>Р</span>
                    <span className={proj.role === 'engineer' ? 'active' : ''} onClick={() => proj.setRole('engineer')}>И</span>
                </div>
            </div>

            {proj.view === 'list' && <ListView proj={proj} onNewProject={proj.openNewProject} />}
            {proj.view === 'overview' && <OverviewView proj={proj} onAskAi={openChat} />}
            {proj.view === 'files' && <FilesView proj={proj} onUpload={proj.openUpload} />}
            {proj.view === 'document' && <DocumentView proj={proj} onAskAi={openChat} />}
            {proj.view === 'queue' && <QueueView proj={proj} />}
            {proj.view === 'archive' && <ArchiveView proj={proj} />}

            {chatOpen && <AssistantChatPanel title={chatTitle} onClose={closeChat} />}

            <UploadChangesetModal proj={proj} />
            <RejectModal proj={proj} />
            <NewProjectModal proj={proj} />
            <PdfPreviewOverlay proj={proj} />
        </div>
    );
}

export default ProjectsPage;
