import React from 'react';

function NoteCapture({ notes }) {
    const canGenerate = notes.rawText.trim().length > 0;

    return (
        <>
            <header className="nt-capture-header">
                <div className="nt-eyebrow accent">Новая заметка</div>
                <div className="nt-capture-title">Наговорите или запишите поток мыслей</div>
                <div className="nt-capture-hint">
                    Пишите как есть, без структуры — цифры, обрывки фраз, что угодно. ИИ соберёт из
                    этого аккуратную заметку с заголовками, списками и таблицами.
                </div>
            </header>

            <div className="nt-capture-body">
                <div className="nt-voice-row">
                    <span
                        className={`nt-voice-btn${notes.voiceOn ? ' on' : ''}`}
                        title="Голосовой ввод"
                        onClick={notes.toggleVoice}
                    >
                        {notes.voiceOn ? '⏺' : '🎙'}
                    </span>
                    <span className="nt-muted">
                        {notes.voiceOn ? 'Слушаю… нажмите ещё раз, чтобы остановить' : 'Нажмите на микрофон для голосового ввода'}
                    </span>
                </div>

                <textarea
                    className="nt-capture-area"
                    value={notes.rawText}
                    onChange={(e) => notes.setRawText(e.target.value)}
                    placeholder="Так, запиши, вчера тестировали насос на стенде номер два, выставили ШИМ на 1.8 вольта, частоту дали 50 герц…"
                />

                <div className="nt-capture-actions">
                    <div
                        className={`nt-generate-btn${canGenerate ? ' ready' : ''}${notes.generating ? ' spinning' : ''}`}
                        onClick={notes.generateNote}
                    >
                        <span className="nt-generate-icon">{notes.generating ? '↻' : '✦'}</span>
                        {notes.generating ? 'Собираю заметку…' : 'Сгенерировать заметку'}
                    </div>
                    <span className="nt-cancel-link" onClick={notes.cancelCapture}>Отменить</span>
                </div>
            </div>
        </>
    );
}

export default NoteCapture;