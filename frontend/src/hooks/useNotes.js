import { useState, useCallback } from 'react';
import { ENDPOINTS } from '../config/api';
import { useApi, useShowError } from '../context/ApiContext';

export const FOLDERS = [
    { id: 'all', label: 'Все заметки', icon: '▤' },
    { id: 'work', label: 'Работа', icon: '◇' },
    { id: 'ideas', label: 'Идеи', icon: '✦' },
    { id: 'personal', label: 'Личное', icon: '○' },
];

export const TAG_PALETTE = [
    { key: 'important', label: 'Важное', dot: '#d65f5f' },
    { key: 'idea', label: 'Идея', dot: '#d9a441' },
    { key: 'todo', label: 'Todo', dot: '#5b9bd5' },
    { key: 'question', label: 'Вопрос', dot: '#9c7fd4' },
    { key: 'ref', label: 'Референс', dot: '#86b98c' },
];

const TAG_BY_KEY = Object.fromEntries(TAG_PALETTE.map((t) => [t.key, t]));

export const tagMeta = (key) => TAG_BY_KEY[key] || { key, label: key, dot: '#7c7264' };

export const notePreview = (content) =>
    (content || '').replace(/^#.*\n?/, '').replace(/[#*`]/g, '').trim().slice(0, 110) || 'Пусто';

export const fmtReminder = (v) => {
    if (!v) return '';
    const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(v);
    if (!m) return v;
    return `${m[3]}.${m[2]} ${m[4]}:${m[5]}`;
};

// Бэкенд отдаёт reminder/updated_at как ISO datetime — datetime-local инпуту и fmtReminder
// нужен голый "YYYY-MM-DDTHH:MM" без секунд/таймзоны.
const toLocalInput = (iso) => (iso ? iso.slice(0, 16) : null);

const fromBackend = (n) => ({
    id: n.note_guid,
    title: n.title || '',
    content: n.content || '',
    folder: n.folder || 'work',
    tags: n.tags || [],
    pinned: n.pinned,
    reminder: toLocalInput(n.reminder),
    followUp: n.follow_up,
    updated: toLocalInput(n.updated_at) ? fmtReminder(n.updated_at) : '',
    chunks: n.chunk_count || 0,
    points: n.chunk_count || 0,
    status: n.status,
    stage: 'edit',
});

const toPatchBody = (n) => ({
    title: n.title,
    content: n.content,
    folder: n.folder,
    tags: n.tags,
    reminder: n.reminder || null,
    pinned: n.pinned,
    follow_up: n.followUp,
});

export function useNotes() {
    const api = useApi();
    const showError = useShowError();
    const [notes, setNotes] = useState([]);
    const [folder, setFolderState] = useState('all');
    const [tagFilter, setTagFilterState] = useState(null);
    const [query, setQuery] = useState('');
    const [activeId, setActiveId] = useState(null);
    const [mode, setMode] = useState('editor');
    const [tagPickerOpen, setTagPickerOpen] = useState(false);
    const [rawText, setRawText] = useState('');
    const [voiceOn, setVoiceOn] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [saveState, setSaveState] = useState('idle');

    const loadNotes = useCallback(async () => {
        try {
            const data = await api.get(ENDPOINTS.NOTES);
            const mapped = (data.notes || []).map(fromBackend);
            setNotes(mapped);
            setActiveId((prev) => prev ?? (mapped[0]?.id ?? null));
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError]);

    const setFolder = useCallback((id) => {
        setFolderState(id);
        setTagFilterState(null);
    }, []);

    const setTagFilter = useCallback((key) => {
        setTagFilterState((prev) => (prev === key ? null : key));
        setFolderState('all');
    }, []);

    const open = useCallback((id) => {
        setActiveId(id);
        setMode('editor');
        setTagPickerOpen(false);
    }, []);

    const togglePin = useCallback((id, e) => {
        e?.stopPropagation?.();
        let nextPinned;
        setNotes((prev) => prev.map((n) => {
            if (n.id !== id) return n;
            nextPinned = !n.pinned;
            return { ...n, pinned: nextPinned };
        }));
        api.patch(ENDPOINTS.NOTE(id), { pinned: nextPinned }).catch((err) => showError(err.message));
    }, [api, showError]);

    const updateActive = useCallback((patch) => {
        setNotes((prev) => prev.map((n) => (n.id === activeId ? { ...n, ...patch, updated: 'только что' } : n)));
    }, [activeId]);

    const toggleFollowUp = useCallback(() => {
        let nextFollowUp;
        setNotes((prev) => prev.map((n) => {
            if (n.id !== activeId) return n;
            nextFollowUp = !n.followUp;
            return { ...n, followUp: nextFollowUp, updated: 'только что' };
        }));
        api.patch(ENDPOINTS.NOTE(activeId), { follow_up: nextFollowUp }).catch((err) => showError(err.message));
    }, [api, showError, activeId]);

    const addTag = useCallback((key) => {
        let nextTags;
        setNotes((prev) => prev.map((n) => {
            if (n.id !== activeId || n.tags.includes(key)) return n;
            nextTags = [...n.tags, key];
            return { ...n, tags: nextTags, updated: 'только что' };
        }));
        setTagPickerOpen(false);
        if (nextTags) api.patch(ENDPOINTS.NOTE(activeId), { tags: nextTags }).catch((err) => showError(err.message));
    }, [api, showError, activeId]);

    const removeTag = useCallback((key) => {
        let nextTags;
        setNotes((prev) => prev.map((n) => {
            if (n.id !== activeId) return n;
            nextTags = n.tags.filter((k) => k !== key);
            return { ...n, tags: nextTags, updated: 'только что' };
        }));
        api.patch(ENDPOINTS.NOTE(activeId), { tags: nextTags }).catch((err) => showError(err.message));
    }, [api, showError, activeId]);

    const createNote = useCallback(async () => {
        try {
            const created = await api.post(ENDPOINTS.NOTES, {
                title: '', content: '', folder: 'work', tags: [], pinned: false, reminder: null, follow_up: false,
            });
            const note = { ...fromBackend(created), stage: 'capture' };
            setNotes((prev) => [note, ...prev]);
            setActiveId(note.id);
            setMode('editor');
            setRawText('');
            setSaveState('idle');
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError]);

    const deleteActive = useCallback(async () => {
        const id = activeId;
        try {
            await api.delete(ENDPOINTS.NOTE(id));
            setNotes((prev) => {
                const rest = prev.filter((n) => n.id !== id);
                setActiveId(rest.length ? rest[0].id : null);
                return rest;
            });
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError, activeId]);

    const cancelCapture = useCallback(() => deleteActive(), [deleteActive]);
    const toggleVoice = useCallback(() => setVoiceOn((v) => !v), []);

    // Бэкенд сам зовёт llm_service и сохраняет результат в заметку — сюда возвращается уже
    // сохранённое состояние, ничего досохранять на фронте не нужно.
    const generateNote = useCallback(async () => {
        if (generating || !rawText.trim() || !activeId) return;
        setGenerating(true);
        try {
            const generated = await api.post(ENDPOINTS.NOTE_GENERATE(activeId), { raw_text: rawText });
            setNotes((prev) => prev.map((n) => (n.id === activeId ? { ...fromBackend(generated), stage: 'edit' } : n)));
            setMode('preview');
        } catch (e) {
            showError(e.message);
        } finally {
            setGenerating(false);
        }
    }, [api, showError, generating, rawText, activeId]);

    const saveAndIndex = useCallback(async () => {
        if (saveState === 'saving') return;
        const id = activeId;
        const note = notes.find((n) => n.id === id);
        if (!note) return;
        setSaveState('saving');
        try {
            const saved = await api.patch(ENDPOINTS.NOTE(id), toPatchBody(note));
            const indexed = await api.post(ENDPOINTS.NOTE_INDEX(id));
            setNotes((prev) => prev.map((n) => (n.id === id ? { ...fromBackend(indexed || saved), stage: 'edit' } : n)));
            setSaveState('saved');
            setTimeout(() => setSaveState((s) => (s === 'saved' ? 'idle' : s)), 1800);
            // Индексация асинхронная (Celery + колбэк в backend) — статус/chunk_count на момент
            // ответа POST /index ещё не финальные, подтягиваем их одним доп. запросом чуть позже.
            setTimeout(() => {
                api.get(ENDPOINTS.NOTE(id))
                    .then((fresh) => setNotes((prev) => prev.map((n) => (n.id === id ? { ...fromBackend(fresh), stage: 'edit' } : n))))
                    .catch(() => {});
            }, 3000);
        } catch (e) {
            showError(e.message);
            setSaveState('idle');
        }
    }, [api, showError, saveState, activeId, notes]);

    return {
        notes, folder, tagFilter, query, activeId, mode, tagPickerOpen,
        rawText, voiceOn, generating, saveState,
        loadNotes,
        setFolder, setTagFilter, setQuery, setMode, open, togglePin,
        updateActive, toggleFollowUp, addTag, removeTag,
        createNote, cancelCapture, deleteActive,
        toggleVoice, setRawText, generateNote, saveAndIndex,
        setTagPickerOpen,
    };
}