import React, { useEffect, useMemo } from 'react';
import NoteList from '../components/notes/NoteList.jsx';
import NoteCapture from '../components/notes/NoteCapture.jsx';
import NoteEditor from '../components/notes/NoteEditor.jsx';
import { useNotes, FOLDERS, TAG_PALETTE } from '../hooks/useNotes';

function NotesPage({ theme }) {
    const notes = useNotes();

    useEffect(() => {
        notes.loadNotes();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const folders = useMemo(() => FOLDERS.map((f) => ({
        ...f,
        count: f.id === 'all' ? notes.notes.length : notes.notes.filter((n) => n.folder === f.id).length,
        active: notes.folder === f.id && !notes.tagFilter,
    })), [notes.notes, notes.folder, notes.tagFilter]);

    const filtered = useMemo(() => {
        let list = notes.notes;
        if (notes.tagFilter) list = list.filter((n) => n.tags.includes(notes.tagFilter));
        else if (notes.folder !== 'all') list = list.filter((n) => n.folder === notes.folder);
        const q = notes.query.trim().toLowerCase();
        if (q) list = list.filter((n) => `${n.title} ${n.content}`.toLowerCase().includes(q));
        return list;
    }, [notes.notes, notes.tagFilter, notes.folder, notes.query]);

    const pinnedNotes = useMemo(() => filtered.filter((n) => n.pinned), [filtered]);
    const restNotes = useMemo(() => filtered.filter((n) => !n.pinned), [filtered]);
    const listTitle = pinnedNotes.length ? 'Остальные' : 'Заметки';
    const isEmpty = pinnedNotes.length === 0 && restNotes.length === 0;

    const activeNote = notes.notes.find((n) => n.id === notes.activeId);
    const isCapture = activeNote?.stage === 'capture';

    const totalPoints = notes.notes.reduce((a, n) => a + n.points, 0);

    return (
        <>
            <aside className="nt-aside">
                <div className="nt-aside-header">
                    <div>
                        <div className="nt-aside-eyebrow">Личное</div>
                        <div className="nt-aside-title">Заметки</div>
                    </div>
                    <div className="nt-new-btn" title="Новая заметка" onClick={notes.createNote}>＋</div>
                </div>

                <div className="nt-aside-search">
                    <span>⌕</span>
                    <input
                        className="field"
                        value={notes.query}
                        onChange={(e) => notes.setQuery(e.target.value)}
                        placeholder="Поиск по заметкам"
                    />
                </div>

                <div className="nt-aside-body">
                    <div className="nt-aside-group-title">Папки</div>
                    {folders.map((f) => (
                        <div
                            key={f.id}
                            className={`nt-folder-item${f.active ? ' active' : ''}`}
                            onClick={() => notes.setFolder(f.id)}
                        >
                            <span className="nt-folder-icon">{f.icon}</span>
                            <span className="nt-folder-label">{f.label}</span>
                            <span className="mono nt-folder-count">{f.count}</span>
                        </div>
                    ))}

                    <div className="nt-aside-group-title">Теги</div>
                    <div className="nt-tag-filters">
                        {TAG_PALETTE.map((tg) => (
                            <span
                                key={tg.key}
                                className={`nt-tag-filter${notes.tagFilter === tg.key ? ' active' : ''}`}
                                onClick={() => notes.setTagFilter(tg.key)}
                            >
                                <span className="nt-tag-dot" style={{ background: tg.dot }} />{tg.label}
                            </span>
                        ))}
                    </div>
                </div>

                <div className="nt-index-summary">
                    <div className="nt-index-summary-title">
                        <span className="kb-ok-dot" />
                        <span>Индекс заметок</span>
                    </div>
                    <div className="kb-index-row"><span>Заметок</span><span key={notes.notes.length} className="mono counter-pop">{notes.notes.length}</span></div>
                    <div className="kb-index-row"><span>Точек в БД</span><span key={totalPoints} className="mono kb-accent counter-pop">{totalPoints}</span></div>
                </div>
            </aside>

            <NoteList
                notes={notes}
                pinnedNotes={pinnedNotes}
                restNotes={restNotes}
                listTitle={listTitle}
                isEmpty={isEmpty}
            />

            <main className="nt-main">
                {isCapture && <NoteCapture notes={notes} />}
                {activeNote && !isCapture && <NoteEditor notes={notes} activeNote={activeNote} theme={theme} />}
                {!activeNote && (
                    <div className="nt-empty-state">
                        <div className="nt-empty-icon">✎</div>
                        <div>Выберите заметку слева или создайте новую</div>
                        <div className="nt-empty-btn" onClick={notes.createNote}>＋ Новая заметка</div>
                    </div>
                )}
            </main>
        </>
    );
}

export default NotesPage;