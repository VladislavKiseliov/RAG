export const PAGE_SIZES = {
  documents: 20,
  users: 25,
  tasks: 12,
};

export const DOC_STATUSES = ['completed', 'processing', 'error'];
export const USER_STATUSES = ['active', 'blocked'];
export const TASK_TABS = ['active', 'completed', 'failed'];

export const SERVICE_LABELS = {
  backend: 'Backend :8000',
  rag: 'RAG Service :8001',
  minio: 'MinIO :9000',
  qdrant: 'Qdrant :6333',
  postgres: 'PostgreSQL :5432',
  redis: 'Redis :6379',
};
