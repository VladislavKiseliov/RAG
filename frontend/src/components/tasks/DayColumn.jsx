import React from 'react';

const PRIORITY_LABEL = { high: 'Высокий', med: 'Средний', low: 'Низкий' };

function DayColumn({ day, onToggle, onDelete, onDraftChange, onDraftSubmit, onOpenSection }) {
    const done = day.tasks.filter((t) => t.done).length;

    return (
        <div className={`tk-day${day.isToday ? ' today' : ''}`}>
            <div className="tk-day-header">
                <span className="tk-day-dow">{day.dow}</span>
                <span className="mono tk-day-date">{day.dateLabel}</span>
            </div>
            <div className="mono tk-day-done">{done}/{day.tasks.length}</div>

            <div className="tk-task-list">
                {day.tasks.map((tk) => (
                    <div key={tk.id} className={`tk-task${tk.done ? ' done' : ''}`}>
                        <div className="tk-task-row">
                            <span
                                className={`tk-task-box${tk.done ? ' done' : ''}`}
                                onClick={() => onToggle(tk.id)}
                            >
                                {tk.done ? '✓' : ''}
                            </span>
                            <div className="tk-task-body">
                                <div className={`tk-task-title${tk.done ? ' done' : ''}`}>{tk.title}</div>
                                <div className="tk-task-meta">
                                    <span className={`tk-prio-dot tk-prio-${tk.priority}`} title={PRIORITY_LABEL[tk.priority]} />
                                    {tk.source && (
                                        <span className="mono tk-task-source kb-accent" onClick={() => onOpenSection(tk.source.section)}>
                                            {tk.source.icon} {tk.source.label}
                                        </span>
                                    )}
                                    {tk.carried && <span className="tk-task-carried">перенесено</span>}
                                </div>
                            </div>
                            {tk.manual && (
                                <span className="tk-task-delete" onClick={() => onDelete(tk.id)}>✕</span>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            <div className="tk-draft-row">
                <input
                    className="field tk-draft-input"
                    value={day.draft}
                    onChange={(e) => onDraftChange(day.iso, e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') onDraftSubmit(day.iso); }}
                    placeholder="+ задача"
                />
            </div>
        </div>
    );
}

export default DayColumn;