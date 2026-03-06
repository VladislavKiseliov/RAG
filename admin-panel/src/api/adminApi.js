import dayjs from 'dayjs';
import { db } from './mockDb';

const wait = (ms = 350) => new Promise((resolve) => setTimeout(resolve, ms));

function paginate(items, page = 1, pageSize = 20) {
  const total = items.length;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const offset = (page - 1) * pageSize;
  return { items: items.slice(offset, offset + pageSize), total, page, pages, pageSize };
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

export async function loginAdminMock(username, password) {
  await wait();
  if (username !== 'admin' || password !== 'admin') {
    throw new Error('Неверный логин или пароль');
  }
  return { role: 'admin', user: { username: 'admin', displayName: 'Admin' } };
}

export async function logoutAdminMock() {
  await wait(120);
  return { ok: true };
}

export async function getStats() {
  await wait();
  const completedDocs = db.documents.filter((d) => d.status === 'completed').length;
  return {
    documents_total: db.documents.length,
    documents_delta_7d: 12,
    users_total: db.users.length,
    users_delta_7d: 3,
    chats_total: db.users.reduce((sum, u) => sum + u.chats_count, 0),
    chats_delta_7d: 87,
    tasks_active: db.tasks.filter((t) => t.status === 'ACTIVE').length,
    activity_7d: Array.from({ length: 7 }).map((_, idx) => ({
      day: dayjs().subtract(6 - idx, 'day').format('DD.MM'),
      documents: Math.max(0, completedDocs % 20 + idx * 2 - 3),
      messages: 80 + idx * 11,
    })),
  };
}

export async function getDocumentStats() {
  await wait(220);
  const completed = db.documents.filter((d) => d.status === 'completed').length;
  const processing = db.documents.filter((d) => d.status === 'processing').length;
  const error = db.documents.filter((d) => d.status === 'error').length;
  return { completed, processing, error, total: db.documents.length };
}

export async function getLatestDocuments(limit = 10) {
  await wait(180);
  return [...db.documents]
    .sort((a, b) => new Date(b.uploaded_at) - new Date(a.uploaded_at))
    .slice(0, limit);
}

export async function getDocuments(params) {
  await wait();
  const {
    page = 1,
    pageSize = 20,
    search = '',
    status = 'all',
    sortBy = 'uploaded_at',
    sortDir = 'desc',
  } = params;

  let rows = [...db.documents];
  if (status !== 'all') rows = rows.filter((d) => d.status === status);
  if (search?.trim().length >= 2) {
    const q = search.trim().toLowerCase();
    rows = rows.filter((d) => d.filename.toLowerCase().includes(q));
  }
  rows = sortByField(rows, sortBy, sortDir);
  return paginate(rows, page, pageSize);
}

export async function getDocumentById(docId) {
  await wait();
  const doc = db.documents.find((d) => d.doc_id === docId);
  if (!doc) throw new Error('Документ не найден');
  return doc;
}

export async function reindexDocument(docId) {
  await wait(300);
  const doc = db.documents.find((d) => d.doc_id === docId);
  if (!doc) throw new Error('Документ не найден');
  doc.status = 'processing';
  doc.error_text = null;
  setTimeout(() => {
    doc.status = 'completed';
    doc.chunk_count = 120 + Math.floor(Math.random() * 50);
  }, 5000);
  return { doc_id: docId, status: 'processing' };
}

export async function deleteDocument(docId) {
  await wait(250);
  const idx = db.documents.findIndex((d) => d.doc_id === docId);
  if (idx === -1) throw new Error('Документ не найден');
  db.documents.splice(idx, 1);
  return { status: 'deleted' };
}

export async function bulkDeleteDocuments(docIds) {
  await wait(320);
  db.documents = db.documents.filter((d) => !docIds.includes(d.doc_id));
  return { deleted: docIds.length };
}

export async function getDownloadUrl(docId) {
  await wait(180);
  return {
    url: `http://minio:9000/documents/${docId}?X-Amz-Expires=900`,
    expires_in: 900,
  };
}

export async function uploadDocuments(files) {
  await wait(400);
  const created = files.map((file) => ({
    doc_id: crypto.randomUUID(),
    filename: file.name,
    status: 'processing',
    chunk_count: null,
    uploaded_at: new Date().toISOString(),
    size_mb: Number((file.size / (1024 * 1024)).toFixed(1)),
    minio_key: `documents/new/${file.name}`,
    file_hash: `sha256:${crypto.randomUUID().replaceAll('-', '')}`,
    embedding_model: 'BAAI/bge-m3',
    collection: 'rag_documents_collection',
    error_text: null,
  }));
  db.documents.unshift(...created);
  setTimeout(() => {
    created.forEach((doc) => {
      doc.status = Math.random() < 0.85 ? 'completed' : 'error';
      doc.chunk_count = doc.status === 'completed' ? 80 + Math.floor(Math.random() * 60) : null;
      doc.error_text = doc.status === 'error' ? 'Ошибка обработки файла' : null;
    });
  }, 3500);
  return created;
}

export async function getUsers(params) {
  await wait();
  const { page = 1, pageSize = 25, search = '', status = 'all', sortBy = 'registered_at', sortDir = 'desc' } = params;
  let rows = [...db.users];
  if (status !== 'all') rows = rows.filter((u) => (status === 'blocked' ? u.is_blocked : !u.is_blocked));
  if (search?.trim().length >= 2) {
    const q = search.trim().toLowerCase();
    rows = rows.filter((u) => u.username.toLowerCase().includes(q));
  }
  rows = sortByField(rows, sortBy, sortDir);
  return paginate(rows, page, pageSize);
}

export async function getUserById(userId) {
  await wait();
  const user = db.users.find((u) => u.user_id === userId);
  if (!user) throw new Error('Пользователь не найден');
  return {
    ...user,
    recent_chats: Array.from({ length: 5 }).map((_, idx) => ({
      chat_id: crypto.randomUUID(),
      title: `Чат ${idx + 1}: рабочий диалог`,
      created_at: dayjs().subtract(idx + 2, 'day').toISOString(),
      messages_count: 8 + idx * 6,
      last_message_at: dayjs().subtract(idx + 1, 'day').toISOString(),
    })),
  };
}

export async function blockUser(userId, isBlocked) {
  await wait(220);
  const user = db.users.find((u) => u.user_id === userId);
  if (!user) throw new Error('Пользователь не найден');
  if (user.username === 'admin') throw new Error('admin нельзя блокировать');
  user.is_blocked = isBlocked;
  return { status: 'ok', is_blocked: isBlocked };
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
  await wait(230);
  db.services.forEach((srv) => {
    if (Math.random() < 0.05) {
      srv.status = 'offline';
      srv.latency_ms = null;
      return;
    }
    const jitter = Math.max(1, (srv.latency_ms || 30) + Math.floor((Math.random() - 0.5) * 20));
    srv.latency_ms = jitter;
    srv.status = jitter > 220 ? 'degraded' : 'online';
  });
  return {
    services: db.services,
    checked_at: new Date().toISOString(),
  };
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
