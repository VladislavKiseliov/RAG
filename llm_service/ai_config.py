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
    summary_system_prompt: str
    chapter_summary_system_prompt: str
    document_summary_system_prompt: str
    table_summary_system_prompt: str
    note_system_prompt: str
    query_expansion_prompt: str


class GatewayConfig(BaseModel):
    """Пороги плана/сравнения документов/реранка, см. ARCHITECTURE.md §3/§10 (шаги 1c/4/5b)."""
    max_docs_interactive: int = 4
    max_subtasks: int = 12
    router_knn_threshold: float = 0.15
    router_confidence_threshold: float = 0.7
    # Стартовые оценки (не откалиброваны eval'ом - см. ARCHITECTURE.md §1 п.3, второе
    # сознательное исключение). Ниже no_data_threshold - retrieval_empty=True, LLM не
    # зовём; между порогами - "серая зона" (сегодня уходит в build_prompt как sufficient,
    # т.к. reflect ещё заглушка); выше grey_zone_threshold - обычный sufficient.
    rerank_no_data_threshold: float = 0.35
    rerank_grey_zone_threshold: float = 0.60


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