import React from 'react';

const SERVICE_LABEL = { backend: 'Backend', rag: 'RAG Service', minio: 'MinIO', qdrant: 'Qdrant', postgres: 'PostgreSQL', redis: 'Redis', flower: 'Flower' };
const STATUS_LABEL = { online: 'В сети', degraded: 'Задержка', offline: 'Недоступен' };
const TASK_STATE_LABEL = { running: 'Выполняется', queued: 'В очереди', success: 'Готово', failed: 'Ошибка' };

function SystemStatusTab({ health, qdrant, tasks, onRevokeTask }) {
    return (
        <div>
            <div className="adm-status-grid">
                {health.map((s) => (
                    <div key={s.name} className="adm-card">
                        <div className="adm-card-label">{SERVICE_LABEL[s.name] || s.name}</div>
                        <div className="adm-card-row">
                            <span className={`status-pill ${s.status}`}><span className="dot" />{STATUS_LABEL[s.status] || s.status}</span>
                            <span className="mono adm-latency">{s.latency_ms == null ? '—' : `${s.latency_ms} ms`}</span>
                        </div>
                    </div>
                ))}
            </div>

            <div className="adm-card">
                <div className="adm-card-title">Статистика Qdrant</div>
                <div className="adm-qdrant-grid">
                    <div>Коллекция <b className="mono">{qdrant.collection}</b></div>
                    <div>Векторов <b className="mono">{qdrant.vectors}</b></div>
                    <div>Сегментов <b className="mono">{qdrant.segments}</b></div>
                    <div>Размер <b className="mono">{qdrant.sizeLabel}</b></div>
                    <div>Optimizer <span className={`status-pill ${qdrant.optimizerOnline ? 'online' : 'offline'}`}><span className="dot" />{qdrant.optimizerOnline ? 'online' : 'offline'}</span></div>
                </div>
            </div>

            <div className="adm-card">
                <div className="adm-card-title">Задачи Celery</div>
                <div className="adm-task-list">
                    {tasks.length === 0 && <div className="adm-empty">Нет задач</div>}
                    {tasks.map((t) => (
                        <div key={t.id} className="adm-task-row">
                            <span className={`task-dot ${t.state}`} />
                            <span className="adm-task-name mono">{t.name}</span>
                            <span className="adm-task-subject">{t.subject}</span>
                            <span className={`adm-task-state ${t.state}`}>{TASK_STATE_LABEL[t.state] || t.state}</span>
                            {(t.state === 'running' || t.state === 'queued') && (
                                <span className="adm-task-cancel" title="Отменить задачу" onClick={() => onRevokeTask(t.id)}>✕</span>
                            )}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

export default SystemStatusTab;