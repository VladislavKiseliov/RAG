import { useState, useCallback } from 'react';

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

// Мок ИИ-трансформации потока мыслей в Markdown-черновик — на проде заменяется
// реальным вызовом LLM с промптом из ЗАМЕТКИ - внедрение.md §2.
const transformRawText = (raw) => {
    const nums = raw.match(/[\d.,]+\s*(вольт|герц|градус\w*|%|мм|см)/gi) || [];
    const title = raw.trim().split(/[.,!?]/)[0].slice(0, 46) || 'Без названия';
    let content = `# ${title}\n\n${raw.trim().replace(/\s+/g, ' ')}\n\n`;
    if (nums.length) {
        content += '## Параметры\n\n';
        nums.forEach((n) => { content += `- ${n.trim()}\n`; });
        content += '\n';
    }
    content += '## Дальнейшие шаги\n\n- Проверить и уточнить детали при следующем осмотре\n- Обновить связанную документацию, если потребуется\n';
    return { title, content };
};

const seedNotes = () => [
    {
        id: 'n1', title: 'Идея: авто-сверка биллинга', folder: 'ideas', tags: ['idea', 'important'], pinned: true,
        reminder: '2026-07-21T10:00', followUp: false, updated: 'сегодня', chunks: 9, points: 9, stage: 'edit',
        content: '# Авто-сверка биллинга\n\nМысль после созвона: сверку с провайдером можно гонять не раз в сутки, а инкрементально по вебхукам.\n\n## Плюсы\n- расхождения видно за минуты, а не на утро\n- меньше нагрузка на батч-джобу в пик\n\n## Риски\n- нужно идемпотентно мёржить события с батч-сверкой\n- провайдер шлёт вебхуки с задержкой до 10 минут\n\nОбсудить с Артёмом на следующем синке.',
    },
    {
        id: 'n2', title: 'Вопросы к архитектору по идентичности', folder: 'work', tags: ['question'], pinned: true,
        reminder: null, followUp: true, updated: 'вчера', chunks: 6, points: 6, stage: 'edit',
        content: '# Вопросы по Identity\n\n- Можно ли делегировать скоуп на 2 уровня (сервис → сервис → сервис)?\n- Что с ревокацией токена при смене роли пользователя посреди сессии?\n- TTL access-токена — фиксированный или настраиваемый per-client?\n\nЗадать на архитектурном созвоне.',
    },
    {
        id: 'n3', title: 'Заметки с ревью PR #482', folder: 'work', tags: ['todo'], pinned: false,
        reminder: null, followUp: false, updated: '2 дня назад', chunks: 4, points: 4, stage: 'edit',
        content: '# Ревью PR #482\n\nПопросил Ивана:\n- вынести retry-логику в отдельную функцию\n- добавить тест на idempotency-key конфликт\n\nСам гляну ещё раз после исправлений.',
    },
    {
        id: 'n4', title: 'Список книг про распределённые системы', folder: 'ideas', tags: ['ref'], pinned: false,
        reminder: null, followUp: false, updated: '3 дня назад', chunks: 5, points: 5, stage: 'edit',
        content: '# Почитать\n\n- Designing Data-Intensive Applications\n- Понять Raft на пальцах — статья, не книга\n- Google SRE book, главы про error budget\n\nНачать с первой, остальное по настроению.',
    },
    {
        id: 'n5', title: 'Идея для onboarding-бота', folder: 'ideas', tags: ['idea'], pinned: false,
        reminder: '2026-07-25T09:30', followUp: false, updated: '4 дня назад', chunks: 7, points: 7, stage: 'edit',
        content: '# Onboarding-бот\n\nБот в мессенджере, который в первую неделю сам присылает чеклист онбординга по дням и пингует наставника, если пункт просрочен.\n\nПроверить, не делает ли уже People-команда что-то похожее.',
    },
    {
        id: 'n6', title: 'Личное: план на отпуск', folder: 'personal', tags: [], pinned: false,
        reminder: null, followUp: false, updated: 'неделю назад', chunks: 3, points: 3, stage: 'edit',
        content: '# Отпуск\n\nПодумать про даты в конце августа, до старта нового квартала. Согласовать с Соней передачу редизайна портала.',
    },
];

// Заметки — пока полностью на клиенте: у rag_service/backend ещё нет домена "заметка"
// (нет ни таблицы, ни эндпоинта), как и было решено для черновой версии Проектов/Админки.
export function useNotes() {
    const [notes, setNotes] = useState(seedNotes);
    const [folder, setFolderState] = useState('all');
    const [tagFilter, setTagFilterState] = useState(null);
    const [query, setQuery] = useState('');
    const [activeId, setActiveId] = useState('n1');
    const [mode, setMode] = useState('editor');
    const [tagPickerOpen, setTagPickerOpen] = useState(false);
    const [rawText, setRawText] = useState('');
    const [voiceOn, setVoiceOn] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [saveState, setSaveState] = useState('idle');

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
        setNotes((prev) => prev.map((n) => (n.id === id ? { ...n, pinned: !n.pinned } : n)));
    }, []);

    const updateActive = useCallback((patch) => {
        setNotes((prev) => prev.map((n) => (n.id === activeId ? { ...n, ...patch, updated: 'только что' } : n)));
    }, [activeId]);

    const toggleFollowUp = useCallback(() => {
        setNotes((prev) => {
            const n = prev.find((x) => x.id === activeId);
            if (!n) return prev;
            return prev.map((x) => (x.id === activeId ? { ...x, followUp: !x.followUp, updated: 'только что' } : x));
        });
    }, [activeId]);

    const addTag = useCallback((key) => {
        setNotes((prev) => prev.map((n) => (n.id === activeId && !n.tags.includes(key)
            ? { ...n, tags: [...n.tags, key], updated: 'только что' }
            : n)));
        setTagPickerOpen(false);
    }, [activeId]);

    const removeTag = useCallback((key) => {
        setNotes((prev) => prev.map((n) => (n.id === activeId
            ? { ...n, tags: n.tags.filter((k) => k !== key), updated: 'только что' }
            : n)));
    }, [activeId]);

    const createNote = useCallback(() => {
        const id = `n${Date.now()}`;
        const note = {
            id, title: '', folder: 'work', tags: [], pinned: false, reminder: null, followUp: false,
            updated: 'только что', chunks: 0, points: 0, content: '', stage: 'capture',
        };
        setNotes((prev) => [note, ...prev]);
        setActiveId(id);
        setMode('editor');
        setRawText('');
        setSaveState('idle');
    }, []);

    const deleteActive = useCallback(() => {
        setNotes((prev) => {
            const rest = prev.filter((n) => n.id !== activeId);
            setActiveId(rest.length ? rest[0].id : null);
            return rest;
        });
    }, [activeId]);

    const cancelCapture = useCallback(() => deleteActive(), [deleteActive]);
    const toggleVoice = useCallback(() => setVoiceOn((v) => !v), []);

    const generateNote = useCallback(() => {
        if (generating || !rawText.trim()) return;
        setGenerating(true);
        setTimeout(() => {
            const { title, content } = transformRawText(rawText);
            updateActive({ title, content, stage: 'edit' });
            setGenerating(false);
            setMode('preview');
        }, 1100);
    }, [generating, rawText, updateActive]);

    // На проде тело запроса — то же, что при загрузке файла в Базу знаний (title/content/owner/
    // chunkSize/overlap), плюс source_type:'note'; chunks/points обновляются из ответа индексатора.
    const saveAndIndex = useCallback(() => {
        if (saveState === 'saving') return;
        setSaveState('saving');
        const id = activeId;
        setTimeout(() => {
            setNotes((prev) => prev.map((n) => (n.id === id
                ? { ...n, stage: 'edit', chunks: Math.max(1, Math.round((n.content || '').length / 220)), points: Math.max(1, Math.round((n.content || '').length / 220)) }
                : n)));
            setSaveState('saved');
            setTimeout(() => setSaveState((s) => (s === 'saved' ? 'idle' : s)), 1800);
        }, 900);
    }, [saveState, activeId]);

    return {
        notes, folder, tagFilter, query, activeId, mode, tagPickerOpen,
        rawText, voiceOn, generating, saveState,
        setFolder, setTagFilter, setQuery, setMode, open, togglePin,
        updateActive, toggleFollowUp, addTag, removeTag,
        createNote, cancelCapture, deleteActive,
        toggleVoice, setRawText, generateNote, saveAndIndex,
        setTagPickerOpen,
    };
}