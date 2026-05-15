1. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

State your assumptions explicitly. If uncertain, ask.
If multiple interpretations exist, present them - don't pick silently.
If a simpler approach exists, say so. Push back when warranted.
If something is unclear, stop. Name what's confusing. Ask.
2. Simplicity First
Minimum code that solves the problem. Nothing speculative.

No features beyond what was asked.
No abstractions for single-use code.
No "flexibility" or "coСуаnfigurability" that wasn't requested.
No error handling for impossible scenarios.
If you write 200 lines and it could be 50, rewrite it.
Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

3. Surgical Changes
Touch only what you must. Clean up only your own mess.

Before any file edit:
1. Read the current file first — always. The user may have edited it since last read.
2. Propose the change and explain what exactly will be added/removed.
3. Wait for explicit approval before writing anything.
Never rewrite a file the user is actively editing. If "file modified since read" error appears — stop, re-read, and re-propose.

When editing existing code:

Don't "improve" adjacent code, comments, or formatting.
Don't refactor things that aren't broken.
Match existing style, even if you'd do it differently.
If you notice unrelated dead code, mention it - don't delete it.
When your changes create orphans:

Remove imports/variables/functions that YOUR changes made unused.
Don't remove pre-existing dead code unless asked.
The test: Every changed line should trace directly to the user's request.

4. Goal-Driven Execution
Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

"Add validation" → "Write tests for invalid inputs, then make them pass"
"Fix the bug" → "Write a test that reproduces it, then make it pass"
"Refactor X" → "Ensure tests pass before and after"
For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## Project: RAGProgramm

Local enterprise AI assistant for internal company documentation. Self-hosted, monorepo.

### Services & Communication
- `frontend` / `admin-panel` → `backend` :8000 (HTTP, все внешние запросы через него)
- `backend` → `llm_service` :8002 (генерация ответа)
- `backend` → `rag_service` :8001 (управление документами, proxy)
- `llm_service` → `rag_service` :8001 (поиск по базе знаний)
- `rag_service` → PostgreSQL, Qdrant, MinIO, Redis
- MinIO → `rag_service` (webhook при загрузке файла)
- Redis → Celery worker (асинхронная обработка документов)

### Architecture
- DDD — логика в доменном и application слое, инфраструктура за интерфейсами (Protocol)
- TDD — новая логика покрывается тестами
- Dependency Injection — зависимости передаются через конструктор, не создаются внутри
- Secrets через pydantic-settings — не os.getenv напрямую, не хардкод