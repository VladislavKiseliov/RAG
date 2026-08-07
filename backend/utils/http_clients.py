import httpx

from backend.settings import settings

RAG_SERVICE_URL = settings.RAG_SERVICE_URL.rstrip("/")

# Общие пулы соединений к внутренним сервисам - раньше admin_routes.py/chats_routes.py/
# knowledge_routes.py/note_service.py открывали httpx.AsyncClient(...) заново на каждый
# вызов (новое TCP-соединение на каждый запрос вместо переиспользуемого пула). Закрываются
# в main.py::lifespan при остановке приложения.
rag_client = httpx.AsyncClient(base_url=RAG_SERVICE_URL, timeout=httpx.Timeout(20.0, connect=5.0))
# admin_routes.py::_proxy_request бьёт то в rag_service, то во Flower по произвольному
# base_url на вызов - в отличие от rag_client, base_url тут не фиксирован.
admin_proxy_client = httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0))
# admin_routes.py::_measure_http - health-пробы сервисов; trust_env=False, чтобы
# случайно не уйти через системный HTTP(S)_PROXY при опросе внутренних docker-хостов.
probe_client = httpx.AsyncClient(trust_env=False)


async def aclose_all() -> None:
    await rag_client.aclose()
    await admin_proxy_client.aclose()
    await probe_client.aclose()
