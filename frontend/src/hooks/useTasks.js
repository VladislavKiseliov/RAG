import { useState, useCallback, useMemo } from 'react';

export const DOW_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
export const MONTH_NAMES = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];

const iso = (dt) => {
    const y = dt.getFullYear(), m = String(dt.getMonth() + 1).padStart(2, '0'), d = String(dt.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
};
const addDays = (isoStr, n) => {
    const dt = new Date(`${isoStr}T00:00:00`);
    dt.setDate(dt.getDate() + n);
    return iso(dt);
};
const mondayOf = (date) => {
    const dt = new Date(date);
    const day = (dt.getDay() + 6) % 7;
    dt.setHours(0, 0, 0, 0);
    dt.setDate(dt.getDate() - day);
    return iso(dt);
};
const todayIso = () => iso(new Date());

// day = ISO "YYYY-MM-DD"; source: {type:'project'|'note', icon, label, section} | null
const seedTasks = () => {
    const base = mondayOf(new Date());
    const d = (n) => addDays(base, n);
    return [
        { id: 'a1', day: d(0), title: 'Финальное ревью миграции v2', priority: 'high', manual: false, done: false, source: { type: 'project', icon: '◫', label: 'Миграция БД', section: 'projects' } },
        { id: 'a2', day: d(0), title: 'Идея: авто-сверка биллинга — обсудить', priority: 'med', manual: false, done: false, source: { type: 'note', icon: '✎', label: 'Заметка', section: 'notes' } },
        { id: 'a3', day: d(0), title: 'Ответить Соне по макетам', priority: 'med', manual: true, done: false, source: null },
        { id: 'a4', day: d(1), title: 'Сверка с провайдером', priority: 'high', manual: false, done: false, source: { type: 'project', icon: '◫', label: 'Биллинг', section: 'projects' } },
        { id: 'a5', day: d(1), title: 'Подготовить слайды для синка', priority: 'low', manual: true, done: true, source: null },
        { id: 'a6', day: d(2), title: 'Обработка частичных возвратов', priority: 'high', manual: false, done: false, source: { type: 'project', icon: '◫', label: 'Платёжный шлюз', section: 'projects' } },
        { id: 'a7', day: d(2), title: 'Купить билеты на конференцию', priority: 'low', manual: true, done: false, source: null },
        { id: 'a8', day: d(3), title: 'Идея для onboarding-бота — набросать план', priority: 'med', manual: false, done: false, source: { type: 'note', icon: '✎', label: 'Заметка', section: 'notes' } },
        { id: 'a9', day: d(4), title: 'Сборка библиотеки компонентов', priority: 'med', manual: false, done: false, source: { type: 'project', icon: '◫', label: 'Редизайн портала', section: 'projects' } },
        { id: 'a10', day: d(4), title: 'Ревью PR #482', priority: 'high', manual: true, done: false, source: null },
    ];
};

// Мок разбора свободного текста в задачу — на проде реальный вызов LLM с промптом из
// ГЛАВНАЯ И ЗАДАЧИ - внедрение.md §2 (title/due_date/priority из текста).
const parseAiTask = (raw) => {
    const lower = raw.toLowerCase();
    let dayOffset = 0;
    if (/послезавтра/.test(lower)) dayOffset = 2;
    else if (/завтра/.test(lower)) dayOffset = 1;
    const priority = /срочно|важно|критично|asap/.test(lower) ? 'high' : /потом|когда-нибудь|неважно/.test(lower) ? 'low' : 'med';
    const title = raw
        .replace(/^(напомни|напиши|запиши|создай задачу|поставь задачу)[,:]?\s*/i, '')
        .replace(/^(завтра|послезавтра|сегодня)\s*/i, '')
        .trim();
    return {
        title: title.charAt(0).toUpperCase() + title.slice(1),
        day: addDays(todayIso(), dayOffset),
        priority,
    };
};

// Задачи — пока полностью на клиенте, как и Заметки/Проекты: у backend/rag_service ещё
// нет домена "задача" (ни таблицы, ни джобы переноса, ни LLM-эндпоинта разбора текста).
export function useTasks() {
    const [weekOffset, setWeekOffset] = useState(0);
    const [tasks, setTasks] = useState(seedTasks);
    const [drafts, setDrafts] = useState({});
    const [aiText, setAiText] = useState('');
    const [aiBusy, setAiBusy] = useState(false);

    const prevWeek = useCallback(() => setWeekOffset((v) => v - 1), []);
    const nextWeek = useCallback(() => setWeekOffset((v) => v + 1), []);
    const thisWeek = useCallback(() => setWeekOffset(0), []);

    const toggleTask = useCallback((id) => {
        setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, done: !t.done } : t)));
    }, []);

    const deleteTask = useCallback((id) => {
        setTasks((prev) => prev.filter((t) => t.id !== id));
    }, []);

    const setDraft = useCallback((dayIso, value) => {
        setDrafts((prev) => ({ ...prev, [dayIso]: value }));
    }, []);

    const addDraftTask = useCallback((dayIso) => {
        setDrafts((prev) => {
            const val = (prev[dayIso] || '').trim();
            if (!val) return prev;
            setTasks((t) => [...t, { id: `m${Date.now()}`, day: dayIso, title: val, priority: 'med', manual: true, done: false, source: null }]);
            return { ...prev, [dayIso]: '' };
        });
    }, []);

    const createAiTask = useCallback(() => {
        if (aiBusy || !aiText.trim()) return;
        const raw = aiText.trim();
        setAiBusy(true);
        setTimeout(() => {
            const parsed = parseAiTask(raw);
            setTasks((prev) => [...prev, { id: `ai${Date.now()}`, ...parsed, manual: true, done: false, source: null }]);
            setAiText('');
            setAiBusy(false);
        }, 850);
    }, [aiBusy, aiText]);

    const weekStart = useMemo(() => addDays(mondayOf(new Date()), weekOffset * 7), [weekOffset]);
    const today = todayIso();
    const dayIsos = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)), [weekStart]);

    // Перенос невыполненных ручных задач на следующий день считается на лету при рендере
    // недели, а не мутирует day у задачи; на проде это полночная джоба на бэкенде (см. TODO).
    const byDay = useMemo(() => {
        const map = {};
        dayIsos.forEach((d) => { map[d] = []; });
        tasks.forEach((t) => { if (map[t.day]) map[t.day].push({ ...t, carried: false }); });
        for (let i = 1; i < dayIsos.length; i++) {
            const prevIso = dayIsos[i - 1];
            tasks.filter((t) => t.day === prevIso && t.manual && !t.done).forEach((t) => {
                if (!map[dayIsos[i]].some((x) => x.id === t.id)) map[dayIsos[i]].push({ ...t, carried: true });
            });
        }
        return map;
    }, [dayIsos, tasks]);

    const days = useMemo(() => dayIsos.map((d) => {
        const dt = new Date(`${d}T00:00:00`);
        return {
            iso: d,
            isToday: d === today,
            dow: DOW_NAMES[(dt.getDay() + 6) % 7],
            dateLabel: `${dt.getDate()} ${MONTH_NAMES[dt.getMonth()]}`,
            tasks: byDay[d],
            draft: drafts[d] || '',
        };
    }), [dayIsos, byDay, drafts, today]);

    const weekDone = days.reduce((a, d) => a + d.tasks.filter((t) => t.done).length, 0);
    const weekTotal = days.reduce((a, d) => a + d.tasks.length, 0);
    const startDt = new Date(`${weekStart}T00:00:00`);
    const endDt = new Date(`${dayIsos[6]}T00:00:00`);
    const weekLabel = `${startDt.getDate()} ${MONTH_NAMES[startDt.getMonth()]} — ${endDt.getDate()} ${MONTH_NAMES[endDt.getMonth()]}`;

    return {
        days,
        weekLabel,
        weekDoneLabel: `${weekDone}/${weekTotal} выполнено`,
        prevWeek,
        nextWeek,
        thisWeek,
        toggleTask,
        deleteTask,
        setDraft,
        addDraftTask,
        aiText,
        setAiText,
        aiBusy,
        createAiTask,
    };
}