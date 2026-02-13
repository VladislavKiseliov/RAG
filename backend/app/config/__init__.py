from .config import *
from .promts import CUSTOM_PROMPT_TEMPLATE

# Определяем что экспортируется при импорте
__all__ = [
    # Пути и директории
    'DIRECTORY_DOCS',
    'QDRANT_URL',
    'COLLECTION_NAME',
    'SQLITE',
    'INGESTION_SERVICE_URL',
    
    # Настройки чанков
    'CHUNK_SIZE',
    'CHUNK_OVERLAP',
    'SIMILARITY_THRESHOLD',
    'MAX_RESULTS',
    
    # Модели
    'EMBEDDING_MODEL_NAME',
    'LLM_MODEL_NAME',
    
    # Объекты
    'text_splitter',
    'parent_splitter',
    'child_splitter',

    
    # Промпты
    'CUSTOM_PROMPT_TEMPLATE'

]
