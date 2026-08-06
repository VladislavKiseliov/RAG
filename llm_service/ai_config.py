from __future__ import annotations

import os
import tomllib
from pathlib import Path

from pydantic import BaseModel

from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.ai_config")

_CONFIG_PATH = Path(__file__).parent / "ai_config.toml"


class LLMConfig(BaseModel):
    model_name: str
    temperature: float
    max_tokens: int


class PromptsConfig(BaseModel):
    system_prompt_rag: str
    system_prompt_chat: str
    general_system_prompt: str
    json_contract_system_prompt: str
    summary_system_prompt: str
    chapter_summary_system_prompt: str
    document_summary_system_prompt: str
    table_summary_system_prompt: str
    note_system_prompt: str
    query_expansion_prompt: str
    plan_prompt: str
    reflect_prompt: str


class GatewayConfig(BaseModel):
    """Пороги плана/сравнения документов/реранка, см. ARCHITECTURE.md §3/§10 (шаги 1c/4/5b)."""
    max_docs_interactive: int = 4
    max_subtasks: int = 4
    # Стартовые оценки (не откалиброваны eval'ом - см. ARCHITECTURE.md §1 п.3, второе
    # сознательное исключение). Ниже no_data_threshold и между порогами ("серая зона") -
    # обе ветки теперь уходят в reflect_node (реальный, см. retrieval_nodes.py) - LLM
    # смотрит на найденное и решает sufficient/need_more/not_in_corpus; выше
    # grey_zone_threshold - обычный sufficient, reflect не вызывается.
    rerank_no_data_threshold: float = 0.35
    rerank_grey_zone_threshold: float = 0.60
    # Кросс-энкодер сортирует, но сам по себе не отсекает - без среза весь найденный
    # пул (включая слабый хвост) доезжает до generate_node, а после накопления между
    # кругами reflect (см. execute_subtasks_node) пул может удвоиться. Больше слабого
    # контекста - больше материала для "додумывания" в ответе (см. §6.9
    # AGENT_GRAPH_CURRENT.md). Стартовая оценка, не откалибрована eval'ом.
    rerank_final_k: int = 6
    # Раньше жили как дефолты аргументов в RetrievalService.retrieve() - правка
    # требовала менять код и пересобирать образ. Вынесены в конфиг вместе с
    # rerank_final_k ради согласованности - все параметры "сколько кандидатов
    # подавать реранкеру" в одном месте, без eval_overrides пока не нужно (ablation
    # ещё не запускали).
    retrieval_top_k_per_query: int = 3
    retrieval_max_parents: int = 6


class AppConfig(BaseModel):
    llm: LLMConfig
    llm_summary: LLMConfig
    prompts: PromptsConfig
    gateway: GatewayConfig = GatewayConfig()

    @classmethod
    def load(cls, filepath: Path | str = _CONFIG_PATH) -> "AppConfig":
        with open(filepath, "rb") as f:
            data = tomllib.load(f)
        return cls(**data)


_last_good_config: AppConfig | None = None
_last_mtime: float = 0.0


def get_live_config() -> AppConfig:
    """Настройки меняются без рестарта, но файл перечитывается только когда его mtime
    реально изменился — os.path.getmtime это атрибут инода из кэша ОС (микросекунды),
    не чтение файла, так что цена проверки на каждый из ~20 вызовов за запрос пренебрежимо мала.
    """
    global _last_good_config, _last_mtime
    try:
        mtime = os.path.getmtime(_CONFIG_PATH)
        if _last_good_config is None or mtime > _last_mtime:
            _last_good_config = AppConfig.load()
            _last_mtime = mtime
    except Exception as e:
        if _last_good_config is None:
            raise
        logger.warning(
            "Ошибка чтения ai_config.toml, используется последний валидный конфиг",
            extra={"error": str(e)},
        )
    return _last_good_config