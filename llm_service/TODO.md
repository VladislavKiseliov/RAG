# LLM Service — TODO

## Критические баги

### 1. Несовпадение схем RetrieveItem с rag_service
`llm_service` ожидает `{child_chunks, parent_chunk, metadata}`, но `rag_service` возвращает `{doc_id, parent_id, score, text, headers}`.

Нужно переписать `RetrieveItem` в `lean_rag_models.py`:
```python
class RetrieveItem(BaseModel):
    doc_id: str
    parent_id: str
    page_num: str | None = None
    score: float
    text: str
    headers: dict[str, Any] = Field(default_factory=dict)
```

После этого поправить `_format_child_chunks_retrive_data` в `lean_rag_agent.py` — убрать `child_chunks` и `parent_chunk`, использовать `item.text`.

---

### 2. agent_routers.py — dict вместо объекта
`final_state` из `ainvoke()` это `dict`, но в роутере используется точечный доступ:
```python
answer_text = final_state.response_model   # AttributeError
context_text = final_state.final_context   # AttributeError
```
Нужно заменить на:
```python
answer_text = final_state.get("response_model", "")
context_text = final_state.get("final_context")
```
Или в `run()` обернуть результат: `return LeanAgentState(**final_state)`

---

### 3. AskResponse — отсутствует поле total
В роутере не передаётся `total` в `AskResponse`, хотя оно required.

---

## Улучшения

### 4. sources не маппируются
В `agent_routers.py` `sources` всегда пустые. Нужно маппить из `retrieval_data`:
```python
sources = [
    SourceItem(doc_id=i.doc_id, parent_id=i.parent_id,
               score=i.score, text=i.text, headers=i.headers)
    for i in final_state.get("retrieval_data", [])
]
```

### 5. Удалить print() из кода
В `LLM_provider.py` (строки 71, 73) остались дебажные `print(1)`, `print(2)`.
