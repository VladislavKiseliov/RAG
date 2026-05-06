function daysAgo(days, minutes = 0) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  d.setMinutes(d.getMinutes() - minutes);
  return d.toISOString();
}

const sampleDocs = Array.from({ length: 73 }).map((_, idx) => {
  const statusPool = ['completed', 'completed', 'completed', 'processing', 'error'];
  const status = statusPool[idx % statusPool.length];
  return {
    doc_id: crypto.randomUUID(),
    filename: `document_${idx + 1}.pdf`,
    status,
    chunk_count: status === 'completed' ? 40 + (idx % 160) : null,
    uploaded_at: daysAgo(Math.floor(idx / 4), idx * 11),
    size_mb: Number((1 + (idx % 20) * 0.7).toFixed(1)),
    s3key: `documents/${idx + 1}/document_${idx + 1}.pdf`,
    file_hash: `sha256:${crypto.randomUUID().replaceAll('-', '')}`,
    embedding_model: 'BAAI/bge-m3',
    collection: 'rag_documents_collection',
    error_text: status === 'error' ? 'Ошибка индексации: не удалось извлечь текст' : null,
  };
});

const sampleUsers = Array.from({ length: 57 }).map((_, idx) => {
  const username = idx === 0 ? 'admin' : `user_${idx}`;
  return {
    user_id: crypto.randomUUID(),
    username,
    is_blocked: idx % 9 === 0 && idx !== 0,
    registered_at: daysAgo(60 - idx),
    chats_count: idx % 16,
    messages_count: (idx % 16) * (10 + (idx % 7)),
    documents_count: idx % 8,
  };
});

const sampleTasks = Array.from({ length: 45 }).map((_, idx) => {
  const statePool = ['ACTIVE', 'SUCCESS', 'FAILURE'];
  const status = statePool[idx % statePool.length];
  const elapsed = `0:0${idx % 6}:${(idx * 7) % 60}`.replace(':0:', ':');
  return {
    task_id: crypto.randomUUID(),
    filename: `document_${idx + 1}.pdf`,
    status,
    elapsed,
    traceback: status === 'FAILURE' ? 'Traceback: ValueError: unsupported file content' : null,
    created_at: daysAgo(Math.floor(idx / 3), idx * 3),
  };
});

const services = [
  { name: 'backend', status: 'online', latency_ms: 45 },
  { name: 'rag', status: 'online', latency_ms: 120 },
  { name: 'minio', status: 'online', latency_ms: 12 },
  { name: 'qdrant', status: 'online', latency_ms: 89 },
  { name: 'postgres', status: 'online', latency_ms: 8 },
  { name: 'redis', status: 'online', latency_ms: 2 },
];

export const db = {
  documents: sampleDocs,
  users: sampleUsers,
  tasks: sampleTasks,
  services,
};
