"""API для экрана «Проекты» — полностью заглушка на in-memory данных, backend'а нет.

Раньше жила в одном файле с knowledge_routes.py (реальным), хотя не имеет с ним ничего
общего кроме соседства в навигации фронта — разнесено, чтобы не путать реальное с фейковым.
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.dependencies import CurrentUserDep

projects_router = APIRouter(prefix="/api/projects", tags=["projects-stub"])

_PROJECTS: list[dict] = [
    {
        "id": "pay", "name": "Платёжный шлюз v2", "glyph": "ПШ", "status": "В работе", "kind": "active",
        "lead": "Ведёт Влад", "deadline": "до 12 июля",
        "desc": "Новая версия платёжного шлюза: переход на идемпотентные операции, поддержка нескольких провайдеров и сверка транзакций.",
        "members": [
            {"init": "ВЛ", "name": "Влад Логинов", "role": "Тимлид"},
            {"init": "ИП", "name": "Иван Петров", "role": "Бэкенд"},
            {"init": "СК", "name": "Соня Кравец", "role": "QA"},
        ],
        "updated": "2 ч назад",
        "tasks": [
            {"t": "Контракт API провайдера", "done": True, "assignee": "ИП"},
            {"t": "Идемпотентность начислений", "done": True, "assignee": "ИП"},
            {"t": "Сверка транзакций (cron)", "done": True, "assignee": "ВЛ"},
            {"t": "Обработка частичных возвратов", "done": False, "assignee": "ВЛ"},
            {"t": "Нагрузочное тестирование", "done": False, "assignee": "СК"},
            {"t": "Документация для интеграторов", "done": False, "assignee": "ВЛ"},
        ],
        "files": [
            {"name": "Спецификация шлюза.pdf", "ext": "PDF", "size": "1.4 МБ", "by": "Влад", "when": "2 ч назад"},
            {"name": "provider-contract.yaml", "ext": "YAML", "size": "24 КБ", "by": "Иван", "when": "вчера"},
            {"name": "Схема сверки.fig", "ext": "FIG", "size": "3.1 МБ", "by": "Соня", "when": "2 дня"},
            {"name": "reconcile.sql", "ext": "SQL", "size": "8 КБ", "by": "Влад", "when": "3 дня"},
            {"name": "Тест-план.docx", "ext": "DOC", "size": "120 КБ", "by": "Соня", "when": "4 дня"},
        ],
        "docs": [
            {"title": "API Reference — Orders v2", "points": 312},
            {"title": "Архитектура сервисов", "points": 268},
        ],
        "activity": [
            {"who": "ИП", "text": "Иван закрыл задачу «Идемпотентность начислений»", "when": "2 часа назад"},
            {"who": "ВЛ", "text": "Влад добавил файл «Спецификация шлюза.pdf»", "when": "2 часа назад"},
            {"who": "СК", "text": "Соня оставила комментарий к тест-плану", "when": "вчера"},
            {"who": "ИП", "text": "Иван открыл ветку feature/multi-provider", "when": "2 дня назад"},
        ],
    },
    {
        "id": "mig", "name": "Миграция БД на v2", "glyph": "МБ", "status": "На ревью", "kind": "review",
        "lead": "Ведёт SRE", "deadline": "до 30 июня",
        "desc": "Перевод схемы базы данных на версию 2 с минимальным даунтаймом: dry-run, посервисный rollout и план отката.",
        "members": [
            {"init": "АР", "name": "Артём Рыжов", "role": "SRE"},
            {"init": "ВЛ", "name": "Влад Логинов", "role": "Ревью"},
        ],
        "updated": "5 ч назад",
        "tasks": [
            {"t": "Снапшот и заморозка схемы", "done": True, "assignee": "АР"},
            {"t": "Dry-run на реплике", "done": True, "assignee": "АР"},
            {"t": "Online-DDL для больших таблиц", "done": True, "assignee": "АР"},
            {"t": "Финальное ревью", "done": False, "assignee": "ВЛ"},
        ],
        "files": [
            {"name": "Runbook миграции.md", "ext": "MD", "size": "180 КБ", "by": "Артём", "when": "5 ч назад"},
            {"name": "migration_v2.sql", "ext": "SQL", "size": "42 КБ", "by": "Артём", "when": "вчера"},
            {"name": "rollback.sql", "ext": "SQL", "size": "18 КБ", "by": "Артём", "when": "вчера"},
        ],
        "docs": [{"title": "Runbook: миграция БД на v2", "points": 96}],
        "activity": [
            {"who": "АР", "text": "Артём отправил проект на ревью", "when": "5 часов назад"},
            {"who": "АР", "text": "Артём приложил rollback.sql", "when": "вчера"},
        ],
    },
    {
        "id": "red", "name": "Редизайн портала", "glyph": "РП", "status": "В работе", "kind": "active",
        "lead": "Ведёт дизайн", "deadline": "до 20 июля",
        "desc": "Обновление инженерного портала: новая структура навигации, тёмная и светлая темы, единая система компонентов.",
        "members": [
            {"init": "СК", "name": "Соня Кравец", "role": "Дизайн"},
            {"init": "ВЛ", "name": "Влад Логинов", "role": "Фронтенд"},
        ],
        "updated": "вчера",
        "tasks": [
            {"t": "Аудит текущих экранов", "done": True, "assignee": "СК"},
            {"t": "Система токенов и тем", "done": True, "assignee": "СК"},
            {"t": "Сборка библиотеки компонентов", "done": False, "assignee": "ВЛ"},
            {"t": "Перенос экранов", "done": False, "assignee": "ВЛ"},
            {"t": "Юзабилити-тест", "done": False, "assignee": "СК"},
        ],
        "files": [
            {"name": "Портал — макеты.fig", "ext": "FIG", "size": "8.2 МБ", "by": "Соня", "when": "вчера"},
            {"name": "Гайд по темам.pdf", "ext": "PDF", "size": "640 КБ", "by": "Соня", "when": "2 дня"},
        ],
        "docs": [{"title": "Гайд по код-стайлу", "points": 64}],
        "activity": [
            {"who": "СК", "text": "Соня обновила макеты в Figma", "when": "вчера"},
            {"who": "ВЛ", "text": "Влад начал сборку компонентов", "when": "2 дня назад"},
        ],
    },
    {
        "id": "ci", "name": "Ускорение CI/CD", "glyph": "CI", "status": "Планирование", "kind": "plan",
        "lead": "Ведёт DevEx", "deadline": "до 5 авг",
        "desc": "Сокращение времени сборки и деплоя: кэширование зависимостей, параллельные джобы и blue-green выкатка.",
        "members": [{"init": "ИП", "name": "Иван Петров", "role": "DevEx"}],
        "updated": "3 дня назад",
        "tasks": [
            {"t": "Замер текущих времён", "done": True, "assignee": "ИП"},
            {"t": "План кэширования", "done": False, "assignee": "ИП"},
            {"t": "Параллелизация тестов", "done": False, "assignee": "ИП"},
        ],
        "files": [{"name": "Метрики сборок.xlsx", "ext": "XLS", "size": "56 КБ", "by": "Иван", "when": "3 дня"}],
        "docs": [{"title": "Руководство по CI/CD", "points": 148}],
        "activity": [{"who": "ИП", "text": "Иван собрал метрики текущих сборок", "when": "3 дня назад"}],
    },
    {
        "id": "bil", "name": "Биллинг", "glyph": "БИ", "status": "В работе", "kind": "active",
        "lead": "Ведёт Влад", "deadline": "до 28 июля",
        "desc": "Запуск сервиса тарификации: модель тарифов, начисления по событиям использования и сверка с провайдером платежей.",
        "members": [
            {"init": "ВЛ", "name": "Влад Логинов", "role": "Тимлид"},
            {"init": "АР", "name": "Артём Рыжов", "role": "Бэкенд"},
        ],
        "updated": "сегодня",
        "tasks": [
            {"t": "Модель тарифных планов", "done": True, "assignee": "ВЛ"},
            {"t": "Начисления по событиям", "done": False, "assignee": "АР"},
            {"t": "Сверка с провайдером", "done": False, "assignee": "АР"},
            {"t": "Отчёты по начислениям", "done": False, "assignee": "ВЛ"},
        ],
        "files": [
            {"name": "Заметки: биллинг.md", "ext": "MD", "size": "64 КБ", "by": "Влад", "when": "сегодня"},
            {"name": "billing-schema.json", "ext": "JSON", "size": "12 КБ", "by": "Артём", "when": "вчера"},
        ],
        "docs": [{"title": "Архитектура сервисов", "points": 268}],
        "activity": [{"who": "ВЛ", "text": "Влад зафиксировал модель тарифов", "when": "сегодня"}],
    },
]


@projects_router.get("")
async def list_projects(current_user: CurrentUserDep):
    return {"projects": _PROJECTS}
