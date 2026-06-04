import dayjs from 'dayjs';
import { db } from './mockDb';
import { httpClient } from './httpClient';

const wait = (ms = 350) => new Promise((resolve) => setTimeout(resolve, ms));

function paginate(items, page = 1, pageSize = 20) {
  const total = items.length;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const offset = (page - 1) * pageSize;
  return { items: items.slice(offset, offset + pageSize), total, page, pages, pageSize };
}

function normalizeUser(u) {
  return {
    user_id: u.id,
    username: u.login,
    is_blocked: false,
    registered_at: u.created_at,
    chats_count: 0,
    messages_count: 0,
    documents_count: 0,
    recent_chats: [],
  };
}

function sortByField(items, sortBy, sortDir = 'desc') {
  const sorted = [...items].sort((a, b) => {
    const av = a[sortBy] ?? '';
    const bv = b[sortBy] ?? '';
    if (typeof av === 'number' && typeof bv === 'number') return av - bv;
    return String(av).localeCompare(String(bv));
  });
  return sortDir === 'asc' ? sorted : sorted.reverse();
}

function toMb(sizeBytes) {
  const bytes = Number(sizeBytes || 0);
  return Number((bytes / (1024 * 1024)).toFixed(1));
}

function normalizeRagDocument(item) {
  const minioKey = item.s3key || item?.meta?.s3key || null;
  const docId = item.doc_id || minioKey || '';

  return {
    doc_id: docId,
    filename: item.filename || 'unknown',
    status: item.status || 'processing',
    chunk_count: item.chunk_count ?? null,
    uploaded_at: item.created_at || new Date().toISOString(),
    size_mb: toMb(item.size || 0),
    size: Number(item.size || 0),
    s3key: minioKey,
    file_hash: item.file_hash || null,
    embedding_model: null,
    collection: null,
    error_text: null,
    meta: item.meta || null,
  };
}

async function fetchDocuments(limit = 1000) {
  const { data } = await httpClient.get('/admin/documents', { params: { limit, offset: 0 } });
  return (Array.isArray(data) ? data : []).map(normalizeRagDocument);
}

async function findDocument(docId) {
  const { data } = await httpClient.get(`/admin/documents/${docId}`);
  return normalizeRagDocument(data);
}

export async function loginAdmin(username, password) {
  const { data } = await httpClient.post('/auth/login', { username, password });
  return {
    role: 'admin',
    user: { username, displayName: 'Admin' },
    access_token: data.access_token,
    refresh_token: data.refresh_token,
  };
}

export async function logoutAdmin(refreshToken) {
  if (!refreshToken) return { ok: true };
  await httpClient.post('/auth/logout', { refresh_token: refreshToken, revoke_all: false });
  return { ok: true };
}

export async function getStats() {
  const [docs, users] = await Promise.all([
    fetchDocuments(),
    getUsers({ page: 1, pageSize: 1 }),
  ]);
  const completedDocs = docs.filter((d) => d.status === 'completed').length;

  return {
    documents_total: docs.length,
    documents_delta_7d: 0,
    users_total: users.total,
    users_delta_7d: 0,
    chats_total: db.users.reduce((sum, u) => sum + u.chats_count, 0),
    chats_delta_7d: 0,
    tasks_active: db.tasks.filter((t) => t.status === 'ACTIVE').length,
    activity_7d: Array.from({ length: 7 }).map((_, idx) => ({
      day: dayjs().subtract(6 - idx, 'day').format('DD.MM'),
      documents: Math.max(0, completedDocs % 20 + idx * 2 - 3),
      messages: 80 + idx * 11,
    })),
  };
}

export async function getDocumentStats() {
  const docs = await fetchDocuments();
  const completed = docs.filter((d) => d.status === 'completed').length;
  const processing = docs.filter((d) => d.status === 'processing').length;
  const error = docs.filter((d) => d.status === 'error').length;
  return { completed, processing, error, total: docs.length };
}

export async function getLatestDocuments(limit = 10) {
  const docs = await fetchDocuments();
  return [...docs]
    .sort((a, b) => new Date(b.uploaded_at) - new Date(a.uploaded_at))
    .slice(0, limit);
}

export async function getDocuments(params) {
  const {
    page = 1,
    pageSize = 20,
    search = '',
    status = 'all',
    sortBy = 'uploaded_at',
    sortDir = 'desc',
  } = params;

  let rows = await fetchDocuments();
  if (status !== 'all') rows = rows.filter((d) => d.status === status);
  if (search?.trim().length >= 2) {
    const q = search.trim().toLowerCase();
    rows = rows.filter((d) => d.filename.toLowerCase().includes(q));
  }
  rows = sortByField(rows, sortBy, sortDir);
  return paginate(rows, page, pageSize);
}

export async function getDocumentById(docId) {
  return await findDocument(docId);
}

export async function reindexDocument(docId) {
  const { data } = await httpClient.post(`/admin/documents/${docId}/reindex`);
  return data;
}

export async function deleteDocument(docId) {
  const { data } = await httpClient.delete(`/admin/documents/${docId}`);
  return data;
}

export async function bulkDeleteDocuments(docIds) {
  const { data } = await httpClient.post('/admin/documents/batch-delete', { doc_ids: docIds });
  return data;
}

export async function getDownloadUrl(docId) {
  const base = (httpClient.defaults.baseURL || '').replace(/\/$/, '');
  return {
    url: `${base}/admin/documents/${docId}/download`,
    expires_in: null,
  };
}

export async function uploadDocuments(files) {
  const created = [];
  const duplicates = [];

  for (const file of files) {
    let data;
    try {
      const res = await httpClient.post('/admin/documents/upload-link', null, {
        params: { filename: file.name, file_size: file.size },
      });
      data = res.data;
    } catch (err) {
      if (err.response?.status === 409) {
        duplicates.push(file.name);
        continue;
      }
      throw err;
    }

    const presignedUrl = data?.presigned_url;
    if (!presignedUrl) throw new Error('Upload link was not returned by backend');

    const putRes = await fetch(presignedUrl, {
      method: 'PUT',
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
      body: file,
    });
    if (!putRes.ok) throw new Error(`Direct upload to storage failed: ${putRes.status}`);

    const uploaded = data?.files?.[0];
    if (!uploaded) continue;

    created.push({
      doc_id: uploaded.doc_id,
      filename: uploaded.filename || file.name,
      status: uploaded.status || 'processing',
      chunk_count: null,
      uploaded_at: new Date().toISOString(),
      size_mb: toMb(uploaded.size || file.size),
      s3key: uploaded.s3key,
      file_hash: null,
      embedding_model: null,
      collection: null,
      error_text: null,
    });
  }
  return { created, duplicates };
}

export async function getUsers(params) {
  const { page = 1, pageSize = 25, search = '', sortBy = 'registered_at', sortDir = 'desc' } = params;
  const { data } = await httpClient.get('/admin/users/repo', { params: { page_size: 500 } });

  let rows = (data?.items || []).map(normalizeUser);
  if (search?.trim().length >= 2) {
    const q = search.trim().toLowerCase();
    rows = rows.filter((u) => u.username.toLowerCase().includes(q));
  }

  rows = sortByField(rows, sortBy, sortDir);
  return paginate(rows, page, pageSize);
}

export async function getUserById(userId) {
  const { data } = await httpClient.get(`/admin/users/repo/${userId}`);
  return normalizeUser(data);
}

export async function createUser(payload) {
  const { data } = await httpClient.post('/admin/users/repo', payload);
  return normalizeUser(data);
}

export async function updateUser(userId, payload) {
  const { data } = await httpClient.put(`/admin/users/repo/${userId}`, payload);
  return normalizeUser(data);
}

export async function deleteUser(userId) {
  const { data } = await httpClient.delete(`/admin/users/repo/${userId}`);
  return data;
}

export async function blockUser(userId, isBlocked) {
  const { data } = await httpClient.patch(`/admin/users/${userId}/block`, { is_blocked: isBlocked });
  return data;
}

export async function getTasks(tab = 'active', page = 1, pageSize = 12) {
  await wait(200);
  const map = { active: 'ACTIVE', completed: 'SUCCESS', failed: 'FAILURE' };
  const status = map[tab] || 'ACTIVE';
  const rows = db.tasks.filter((t) => t.status === status);
  return paginate(rows, page, pageSize);
}

export async function cancelTask(taskId) {
  await wait(180);
  const task = db.tasks.find((t) => t.task_id === taskId);
  if (!task) throw new Error('Задача не найдена');
  task.status = 'FAILURE';
  task.traceback = 'Task revoked by admin';
  return { status: 'revoked' };
}

export async function getHealth() {
  const { data } = await httpClient.get('/admin/system/health');
  return data;
}

export async function getQdrantStats() {
  await wait(150);
  return {
    collection: 'rag_documents_collection',
    vectors_count: 18432,
    segments_count: 4,
    disk_data_size_mb: 145,
    optimizer_status: 'ok',
  };
}
