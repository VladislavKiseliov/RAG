import React from 'react';
import { tagMeta, notePreview, fmtReminder } from '../../hooks/useNotes';

function NoteCard({ note, isActive, isPinned, onOpen, onTogglePin }) {
    return (
        <div
            className={`nt-card${isActive ? ' active' : ''}`}
            onClick={() => onOpen(note.id)}
        >
            <div className="nt-card-row">
                {isPinned ? (
                    <span className="nt-card-pin pinned">★</span>
                ) : (
                    <span className="nt-card-pin" onClick={(e) => onTogglePin(note.id, e)}>☆</span>
                )}
                <span className="nt-card-title">{note.title || 'Без названия'}</span>
                <span className="nt-card-updated">{note.updated}</span>
            </div>
            <div className="nt-card-preview">{notePreview(note.content)}</div>
            <div className="nt-card-tags">
                {note.tags.map((key) => {
                    const tg = tagMeta(key);
                    return (
                        <span key={key} className="nt-tag-label" style={{ color: tg.dot }}>
                            <span className="nt-tag-dot" style={{ background: tg.dot }} />{tg.label}
                        </span>
                    );
                })}
                {note.reminder && (
                    <span className="nt-card-reminder mono">⏰ {fmtReminder(note.reminder)}</span>
                )}
            </div>
        </div>
    );
}

function NoteList({ notes, pinnedNotes, restNotes, listTitle, isEmpty }) {
    return (
        <section className="nt-list">
            {pinnedNotes.length > 0 && (
                <>
                    <div className="nt-list-group-title accent">Закреплённые</div>
                    {pinnedNotes.map((n) => (
                        <NoteCard
                            key={n.id}
                            note={n}
                            isActive={n.id === notes.activeId}
                            isPinned
                            onOpen={notes.open}
                            onTogglePin={notes.togglePin}
                        />
                    ))}
                </>
            )}

            <div className="nt-list-group-title">{listTitle}</div>
            {restNotes.map((n) => (
                <NoteCard
                    key={n.id}
                    note={n}
                    isActive={n.id === notes.activeId}
                    isPinned={false}
                    onOpen={notes.open}
                    onTogglePin={notes.togglePin}
                />
            ))}

            {isEmpty && <div className="nt-list-empty">Ничего не найдено</div>}
        </section>
    );
}

export default NoteList;