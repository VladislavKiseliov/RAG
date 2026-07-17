import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { tagMeta, TAG_PALETTE } from '../../hooks/useNotes';

function NoteEditor({ notes, activeNote, theme }) {
    const availableTags = TAG_PALETTE.filter((p) => !activeNote.tags.includes(p.key));
    const saveLabel = notes.saveState === 'saving'
        ? 'Индексация…'
        : notes.saveState === 'saved' ? 'Сохранено ✓' : 'Сохранить и индексировать';
    const saveIcon = notes.saveState === 'saving' ? '↻' : notes.saveState === 'saved' ? '✓' : '⬇';

    return (
        <>
            <header className="nt-editor-header">
                <div className="nt-editor-title-row">
                    <input
                        className="field nt-title-input"
                        value={activeNote.title}
                        onChange={(e) => notes.updateActive({ title: e.target.value })}
                        placeholder="Без названия"
                    />
                    <span
                        className={`nt-pin-toggle${activeNote.pinned ? ' pinned' : ''}`}
                        title="Закрепить"
                        onClick={() => notes.togglePin(activeNote.id)}
                    >
                        {activeNote.pinned ? '★' : '☆'}
                    </span>
                    <span className="nt-delete-btn" title="Удалить" onClick={notes.deleteActive}>🗑</span>
                </div>

                <div className="nt-editor-meta-row">
                    {activeNote.tags.map((key) => {
                        const tg = tagMeta(key);
                        return (
                            <span key={key} className="nt-tag-chip">
                                <span className="nt-tag-dot" style={{ background: tg.dot }} />
                                {tg.label}
                                <span className="nt-tag-remove" onClick={() => notes.removeTag(key)}>✕</span>
                            </span>
                        );
                    })}
                    <span className="nt-tag-add" onClick={() => notes.setTagPickerOpen((v) => !v)}>＋ тег</span>

                    <span className="nt-meta-spacer">
                        <input
                            type="datetime-local"
                            className="field mono nt-reminder-input"
                            value={activeNote.reminder || ''}
                            onChange={(e) => notes.updateActive({ reminder: e.target.value || null })}
                            style={{ colorScheme: theme === 'dark' ? 'dark' : 'light' }}
                        />
                        <span
                            className={`nt-followup-chip${activeNote.followUp ? ' active' : ''}`}
                            onClick={notes.toggleFollowUp}
                        >
                            📌 на потом
                        </span>
                    </span>
                </div>

                {notes.tagPickerOpen && (
                    <div className="nt-tag-palette">
                        {availableTags.map((p) => (
                            <span key={p.key} className="nt-tag-chip pickable" onClick={() => notes.addTag(p.key)}>
                                <span className="nt-tag-dot" style={{ background: p.dot }} />{p.label}
                            </span>
                        ))}
                    </div>
                )}
            </header>

            <div className="nt-mode-row">
                <div className="nt-mode-tabs">
                    <button className={notes.mode === 'editor' ? 'active' : ''} onClick={() => notes.setMode('editor')}>Редактор</button>
                    <button className={notes.mode === 'preview' ? 'active' : ''} onClick={() => notes.setMode('preview')}>Превью</button>
                </div>
                <span className="mono nt-chunk-badge">▦ {activeNote.chunks} чанк. · ◆ {activeNote.points} точ.</span>
                <div className={`nt-save-btn${notes.saveState === 'saved' ? ' saved' : ''}${notes.saveState === 'saving' ? ' spinning' : ''}`} onClick={notes.saveAndIndex}>
                    <span className="nt-save-icon">{saveIcon}</span>{saveLabel}
                </div>
            </div>

            <div className="nt-editor-body">
                {notes.mode === 'editor' && (
                    <textarea
                        className="nt-content-area"
                        value={activeNote.content}
                        onChange={(e) => notes.updateActive({ content: e.target.value })}
                        placeholder="Пишите в Markdown: # заголовки, - списки, `код`…"
                    />
                )}
                {notes.mode === 'preview' && (
                    <div className="nt-preview message-markdown">
                        {activeNote.content.trim() ? (
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{activeNote.content}</ReactMarkdown>
                        ) : (
                            <p className="nt-muted">Пусто. Начните писать в редакторе.</p>
                        )}
                    </div>
                )}
            </div>
        </>
    );
}

export default NoteEditor;