import { useState, useCallback } from 'react';
import { ENDPOINTS } from '../config/api';
import { useApi, useShowError } from '../context/ApiContext';
import { formatBytes } from '../utils/formatBytes';

export function useProjects() {
    const api = useApi();
    const showError = useShowError();
    const [projects, setProjects] = useState([]);
    const [view, setView] = useState('list');
    const [selectedId, setSelectedId] = useState(null);

    const loadProjects = useCallback(async () => {
        try {
            const data = await api.get(ENDPOINTS.PROJECTS);
            setProjects(data.projects || []);
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError]);

    const openProject = useCallback((id) => {
        setSelectedId(id);
        setView('detail');
    }, []);

    const back = useCallback(() => {
        setSelectedId(null);
        setView('list');
    }, []);

    const toggleTask = useCallback((projectId, taskIndex) => {
        setProjects((prev) => prev.map((p) => {
            if (p.id !== projectId) return p;
            return {
                ...p,
                tasks: p.tasks.map((t, i) => (i !== taskIndex ? t : { ...t, done: !t.done })),
            };
        }));
    }, []);

    const addFile = useCallback((projectId, files) => {
        const added = files.map((f) => {
            const ext = (f.name.split('.').pop() || 'file').toUpperCase().slice(0, 4);
            return {
                name: f.name,
                ext,
                size: formatBytes(f.size),
                by: 'Вы',
                when: 'только что',
                fresh: true,
            };
        });
        setProjects((prev) => prev.map((p) => (p.id !== projectId ? p : { ...p, files: [...added, ...p.files] })));
    }, []);

    return {
        projects,
        view,
        selectedId,
        loadProjects,
        openProject,
        back,
        toggleTask,
        addFile,
    };
}
