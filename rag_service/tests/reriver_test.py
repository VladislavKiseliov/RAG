import asyncio
from rag_service.infrastructure import build_rag_infrastructure

engine, search_service, ingestion_service, minio_provider = build_rag_infrastructure()

async def main():
    result = await search_service.search(query="Что должно быть реализованно в системе ОИ Б")
    print(result)

asyncio.run(main())