from __future__ import annotations

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
    query_expansion_prompt: str


class AppConfig(BaseModel):
    llm: LLMConfig
    prompts: PromptsConfig

    @classmethod
    def load(cls, filepath: Path | str = _CONFIG_PATH) -> "AppConfig":
        with open(filepath, "rb") as f:
            data = tomllib.load(f)
        return cls(**data)


_last_good_config: AppConfig | None = None


def get_live_config() -> AppConfig:
    """Перечитывает ai_config.toml на каждый вызов, чтобы настройки менялись без рестарта."""
    global _last_good_config
    try:
        _last_good_config = AppConfig.load()
    except Exception as e:
        if _last_good_config is None:
            raise
        logger.warning(
            "Ошибка чтения ai_config.toml, используется последний валидный конфиг",
            extra={"error": str(e)},
        )
    return _last_good_config