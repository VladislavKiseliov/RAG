import { useState, useCallback } from 'react';
import { ENDPOINTS } from '../config/api';
import { useApi, useShowError } from '../context/ApiContext';
import { formatBytes } from '../utils/formatBytes';

// rag_service хранит один общий коллекшн без концепции "личных" документов — моки до появления scope/ownerId.
const MOCK_PERSONAL_DOCS = [
    { id: 'mock-p1', title: 'Личные заметки по проекту «Аврора»', owner: 'И. Смирнова', ownerId: 'u-1', scope: 'personal', chunks: 34, points: 34, size: '1.1 МБ', state: 'indexed' },
    { id: 'mock-p2', title: 'Черновик договора с подрядчиком', owner: 'А. Петров', ownerId: 'u-2', scope: 'personal', chunks: 12, points: 12, size: '340 КБ', state: 'processing' },
];

const MOCK_QDRANT = { collection: 'rag_documents', vectors: 18432, segments: 4, sizeLabel: '145 МБ', optimizerOnline: true };

const toAdminDoc = (raw) => ({
    id: raw.doc_id,
    title: raw.filename || 'unknown',
    owner: '—',
    ownerId: undefined,
    scope: 'shared',
    chunks: raw.chunk_count ?? null,
    points: raw.chunk_count ?? null,
    size: formatBytes(raw.size),
    state: raw.status === 'completed' ? 'indexed' : 'processing',
});

// Состояния Celery -> 4 состояния, под которые уже стилизована вкладка (adm-task-*/task-dot).
const TASK_STATE_MAP = {
    PENDING: 'queued',
    RECEIVED: 'queued',
    STARTED: 'running',
    RETRY: 'running',
    SUCCESS: 'success',
    FAILURE: 'failed',
    REVOKED: 'failed',
};

const toAdminTask = ([id, raw]) => ({
    id,
    name: raw.name || 'unknown',
    subject: (raw.args || '').replace(/^[([]|[)\]]$/g, '').slice(0, 60),
    state: TASK_STATE_MAP[raw.state] || 'queued',
    timestamp: raw.timestamp || raw.received || raw.started || 0,
});

const toAdminUser = (raw) => ({
    id: raw.id,
    name: raw.login,
    email: '—',
    isAdmin: raw.role === 'admin',
    docsCount: null,
    lastActiveLabel: '—',
    active: true,
});

export function useAdmin() {
    const api = useApi();
    const showError = useShowError();
    const [tab, setTab] = useState('system');
    const [docScope, setDocScope] = useState('shared');
    const [personalUserId, setPersonalUserId] = useState(null);
    const [userPickerOpen, setUserPickerOpen] = useState(false);
    const [userPickerQuery, setUserPickerQuery] = useState('');
    const [docQuery, setDocQuery] = useState('');
    const [editingDocId, setEditingDocId] = useState(null);

    const [health, setHealth] = useState(null);
    const [documents, setDocuments] = useState([]);
    const [users, setUsers] = useState([]);
    const [tasks, setTasks] = useState([]);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);

    const loadHealth = useCallback(async () => {
        try {
            const data = await api.get(ENDPOINTS.ADMIN_HEALTH);
            setHealth(data.services || []);
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError]);

    const loadDocuments = useCallback(async () => {
        try {
            const data = await api.get(`${ENDPOINTS.ADMIN_DOCUMENTS}?limit=500`);
            setDocuments((Array.isArray(data) ? data : []).map(toAdminDoc));
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError]);

    const loadUsers = useCallback(async () => {
        try {
            const data = await api.get(`${ENDPOINTS.ADMIN_USERS}?page_size=500`);
            setUsers((data.items || []).map(toAdminUser));
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError]);

    const loadTasks = useCallback(async () => {
        try {
            const data = await api.get(ENDPOINTS.ADMIN_TASKS);
            const list = Object.entries(data || {}).map(toAdminTask);
            list.sort((a, b) => b.timestamp - a.timestamp);
            setTasks(list);
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError]);

    const revokeTask = useCallback(async (taskId) => {
        try {
            await api.post(ENDPOINTS.ADMIN_TASK_REVOKE(taskId));
            await loadTasks();
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError, loadTasks]);

    const loadAll = useCallback(async () => {
        setLoading(true);
        await Promise.all([loadHealth(), loadDocuments(), loadUsers(), loadTasks()]);
        setLoading(false);
    }, [loadHealth, loadDocuments, loadUsers, loadTasks]);

    const reindexDocument = useCallback(async (docId) => {
        try {
            await api.post(ENDPOINTS.ADMIN_DOCUMENT_REINDEX(docId));
            await loadDocuments();
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError, loadDocuments]);

    const deleteDocument = useCallback(async (docId) => {
        try {
            await api.delete(ENDPOINTS.ADMIN_DOCUMENT_DELETE(docId));
            setDocuments((prev) => prev.filter((d) => d.id !== docId));
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError]);

    const uploadDocuments = useCallback(async (files) => {
        setUploading(true);
        const results = await Promise.allSettled(files.map(async (file) => {
            const params = new URLSearchParams({ filename: file.name, file_size: String(file.size) });
            const { presigned_url: presignedUrl } = await api.post(`${ENDPOINTS.ADMIN_DOCUMENT_UPLOAD_LINK}?${params}`);
            const putRes = await fetch(presignedUrl, {
                method: 'PUT',
                headers: { 'Content-Type': file.type || 'application/octet-stream' },
                body: file,
            });
            if (!putRes.ok) throw new Error(`${file.name}: не удалось загрузить в хранилище (${putRes.status})`);
        }));
        const failed = results.filter((r) => r.status === 'rejected');
        if (failed.length) showError(failed.map((r) => r.reason?.message || String(r.reason)).join('; '));
        await loadDocuments();
        setUploading(false);
    }, [api, showError, loadDocuments]);

    // Переименование не персистится — на rag_service нет эндпоинта смены заголовка.
    const renameDocumentLocal = useCallback((docId, title) => {
        setDocuments((prev) => prev.map((d) => (d.id === docId ? { ...d, title } : d)));
    }, []);

    const toggleUserRole = useCallback(async (userId, isAdmin) => {
        try {
            await api.patch(ENDPOINTS.ADMIN_USER_ROLE(userId), { is_superuser: !isAdmin });
            setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, isAdmin: !isAdmin } : u)));
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError]);

    // Блокировка — локальный toggle без запроса, т.к. на бэке нет PATCH /admin/users/{id}/block.
    const toggleUserActiveLocal = useCallback((userId) => {
        setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, active: !u.active } : u)));
    }, []);

    return {
        tab, setTab,
        docScope, setDocScope,
        personalUserId, setPersonalUserId,
        userPickerOpen, setUserPickerOpen,
        userPickerQuery, setUserPickerQuery,
        docQuery, setDocQuery,
        editingDocId, setEditingDocId,
        loading,
        uploading,
        health: health || [],
        documents,
        personalDocuments: MOCK_PERSONAL_DOCS,
        users,
        tasks,
        qdrant: MOCK_QDRANT,
        loadAll,
        reindexDocument,
        deleteDocument,
        uploadDocuments,
        renameDocumentLocal,
        toggleUserRole,
        toggleUserActiveLocal,
        revokeTask,
    };
}