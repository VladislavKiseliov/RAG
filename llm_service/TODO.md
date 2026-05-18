# LLM Service — TODO

  ## Критические (без этого ничего не работает)

  ### 1. RetrieveItem схема — ValidationError на каждом RAG-запросе
  rag_service возвращает плоский {doc_id, text, score, headers},
  llm_service ожидает {child_chunks, parent_chunk, metadata}.
  Нужно обновить rag_service:
  - schemas.py — заменить RetrievedChunk на вложенную схему
  - retrieve_service.py — переписать build_retrieved_items под новый формат

  ### 2. route не доходит до generate()
  LLM_provider использует data_prompt.route, но FinalPromptData не имеет поля route.
  Нужно: добавить route в FinalPromptData (в lean_rag_models.py)
  и прокинуть его в build_prompt_node из state.route.

  ## Средние

  ### 3. sources всегда [] в agent_routers.py
  Маппить из final_state["retrieval_data"] → SourceItem.
  total = len(sources).

  ### 4. Дебажные print()
  - lean_rag_agent.py — 3 штуки в expand_queries_node
  - retrieve_service.py — 5 штук в search() и retrieve()

  ## Мелкие

  ### 5. context type mismatch при include_context=True
  final_context это dict, AskResponse.context ожидает str.
