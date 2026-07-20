import React from 'react';
import DayColumn from '../components/tasks/DayColumn.jsx';
import { useTasks } from '../hooks/useTasks';

function TasksPage({ onSelectSection }) {
    const tasks = useTasks();

    return (
        <main className="tk-main">
            <header className="tk-header">
                <div>
                    <div className="tk-eyebrow">Задачи на неделю</div>
                    <div className="tk-title">{tasks.weekLabel}</div>
                </div>
                <div className="tk-week-nav">
                    <span className="mono tk-week-done">{tasks.weekDoneLabel}</span>
                    <div className="tk-week-switch">
                        <div onClick={tasks.prevWeek}>‹</div>
                        <div onClick={tasks.thisWeek}>Эта неделя</div>
                        <div onClick={tasks.nextWeek}>›</div>
                    </div>
                </div>
            </header>

            <div className="tk-ai-bar">
                <span className="kb-accent">✦</span>
                <input
                    className="field tk-ai-input"
                    value={tasks.aiText}
                    onChange={(e) => tasks.setAiText(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') tasks.createAiTask(); }}
                    placeholder="Напишите ИИ, что нужно сделать — например «напомни завтра проверить прошивку STM32»"
                />
                <div
                    className={`tk-ai-btn${tasks.aiText.trim() ? ' active' : ''}${tasks.aiBusy ? ' busy' : ''}`}
                    onClick={tasks.createAiTask}
                >
                    <span className="tk-ai-btn-icon">{tasks.aiBusy ? '↻' : '＋'}</span>
                    {tasks.aiBusy ? 'Создаю…' : 'Создать задачу'}
                </div>
            </div>

            <div className="tk-week-row">
                {tasks.days.map((day) => (
                    <DayColumn
                        key={day.iso}
                        day={day}
                        onToggle={tasks.toggleTask}
                        onDelete={tasks.deleteTask}
                        onDraftChange={tasks.setDraft}
                        onDraftSubmit={tasks.addDraftTask}
                        onOpenSection={onSelectSection}
                    />
                ))}
            </div>
        </main>
    );
}

export default TasksPage;