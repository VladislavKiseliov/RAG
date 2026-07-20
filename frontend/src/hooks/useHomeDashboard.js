import { useState, useCallback, useMemo } from 'react';

// Мок глобального поиска — на проде либо единый индекс, либо 3 параллельных запроса
// (чаты/доки/заметки), см. ГЛАВНАЯ И ЗАДАЧИ - внедрение.md §1.
const SEARCH_INDEX = [
    { title: 'API Reference — Orders v2', subtitle: 'База знаний · Платформа', icon: '▤', kindLabel: 'документ', section: 'knowledge' },
    { title: 'Заметки с ревью PR #482', subtitle: 'Заметки · обновлено 2 дня назад', icon: '✎', kindLabel: 'заметка', section: 'notes' },
    { title: 'Платёжный шлюз v2', subtitle: 'Проекты · в работе', icon: '◫', kindLabel: 'проект', section: 'projects' },
    { title: 'Соня Кравец', subtitle: 'Чаты · «макеты обновила, гляньте»', icon: '✦', kindLabel: 'чат', section: 'chats' },
    { title: 'Руководство по CI/CD', subtitle: 'База знаний · DevEx', icon: '▤', kindLabel: 'документ', section: 'knowledge' },
    { title: 'Идея: авто-сверка биллинга', subtitle: 'Заметки · закреплено', icon: '✎', kindLabel: 'заметка', section: 'notes' },
];

const QUICK_LINKS = [
    { section: 'chats', icon: '✦', stat: '3 непрочитанных' },
    { section: 'knowledge', icon: '▤', stat: '1259 точек в БД' },
    { section: 'projects', icon: '◫', stat: '5 на вас' },
    { section: 'notes', icon: '✎', stat: '2 напоминания' },
];

const NOTIFICATIONS = [
    { icon: '✦', who: 'Соня Кравец', text: 'упомянула вас в «Редизайн портала»', when: '12 минут назад', kind: 'mention', section: 'chats' },
    { icon: '▤', who: 'Иван Петров', text: 'загрузил документ «provider-contract.yaml»', when: '40 минут назад', kind: 'file', section: 'knowledge' },
    { icon: '◫', who: 'Артём Рыжов', text: 'отправил «Миграцию БД» на ревью', when: '2 часа назад', kind: 'review', section: 'projects' },
    { icon: '✦', who: 'Иван Петров', text: 'ответил в общем чате команды', when: 'вчера', kind: 'mention', section: 'chats' },
    { icon: '✎', who: 'Система', text: 'заметка «Вопросы к архитектору» проиндексирована', when: 'вчера', kind: 'system', section: 'notes' },
];

const REMINDERS_SEED = [
    { title: 'Идея: авто-сверка биллинга', dueLabel: 'сегодня, 10:00', urgent: true },
    { title: 'Идея для onboarding-бота', dueLabel: '25.07', urgent: false },
];

const MY_TASKS_SEED = [
    { id: 't1', title: 'Обработка частичных возвратов', project: 'Платёжный шлюз', done: false },
    { id: 't2', title: 'Финальное ревью миграции v2', project: 'Миграция БД', done: false },
    { id: 't3', title: 'Сборка библиотеки компонентов', project: 'Редизайн портала', done: false },
    { id: 't4', title: 'Сверка с провайдером', project: 'Биллинг', done: false },
    { id: 't5', title: 'Контракт API провайдера', project: 'Платёжный шлюз', done: true },
];

const greetingWord = () => {
    const hour = new Date().getHours();
    if (hour < 6) return 'Доброй ночи';
    if (hour < 12) return 'Доброе утро';
    if (hour < 18) return 'Добрый день';
    return 'Добрый вечер';
};

export function useHomeDashboard() {
    const [query, setQuery] = useState('');
    const [myTasks, setMyTasks] = useState(MY_TASKS_SEED);

    const toggleTask = useCallback((id) => {
        setMyTasks((prev) => prev.map((t) => (t.id === id ? { ...t, done: !t.done } : t)));
    }, []);

    const searchResults = useMemo(() => {
        const q = query.trim().toLowerCase();
        if (!q) return [];
        return SEARCH_INDEX.filter((r) => `${r.title} ${r.subtitle}`.toLowerCase().includes(q));
    }, [query]);

    return {
        greeting: greetingWord(),
        query,
        setQuery,
        searchResults,
        quickLinks: QUICK_LINKS,
        notifications: NOTIFICATIONS,
        reminders: REMINDERS_SEED,
        myTasks,
        toggleTask,
    };
}