# Перенос проекта на новое устройство

Инструкция для случая «взять текущий рабочий стенд (с данными, GPU-обработкой документов и
публичным доменом) и поднять то же самое на другом ПК». Для установки с нуля без переноса
данных см. `README.md → Быстрый старт`.

---

## 1. Что поставить на новом устройстве заранее

- **Docker Desktop** (Windows — с включённым WSL2-бэкендом)
- **NVIDIA-драйвер + NVIDIA Container Toolkit** — обязательно, если нужен GPU (обработка
  документов `rag-worker`, эмбеддер/реранкер `tei`/`tei-reranker` — все три требуют GPU в
  `docker-compose.full.yml`). Без этого GPU-контейнеры не запустятся.
- **Git**
- **OpenSSH-клиент** — для туннеля к домену, в Windows 10/11 обычно уже встроен

## 2. Скопировать со старого устройства (вручную, не через git)

| Что | Откуда | Куда |
|---|---|---|
| `.env` | корень репозитория | корень репозитория на новом устройстве |
| SSH-ключ | `C:\Users\rgg1\Downloads\privatekey-1083073.pem` | тот же путь на новом устройстве (или свой путь — тогда поправить его в `run_rag_tunnel.bat`/`start_local_full.bat`) |

Оба файла — не в git, копировать напрямую (флешка/защищённая передача, не через мессенджер в
открытом виде — это секреты и приватный ключ).

## 3. Клонировать репозиторий

```bash
git clone <адрес репозитория>
cd RagProgramm
```

Держи имя папки `RagProgramm` — от него зависит префикс имён Docker-volume'ов (см. шаг 5), иначе
восстановленные данные не попадут в те volume'ы, которые ждёт `docker-compose.full.yml`.

Положи скопированный `.env` в корень.

## 4. Создать внешний volume для Redis

`ragprogramm_redis_data` в `docker-compose.full.yml` объявлен как `external: true` — Compose
его сам не создаст, и `docker compose up` упадёт с ошибкой, если не создать заранее:

```bash
docker volume create ragprogramm_redis_data
```

## 5. Перенести данные (если нужны существующие документы/чаты, а не чистый старт)

**На старом устройстве** — упаковать volume'ы в архивы:

```bash
docker run --rm -v ragprogramm_postgres_data:/data -v %cd%:/backup alpine tar czf /backup/postgres_data.tar.gz -C /data .
docker run --rm -v ragprogramm_minio_data:/data -v %cd%:/backup alpine tar czf /backup/minio_data.tar.gz -C /data .
docker run --rm -v ragprogramm_qdrant_data:/data -v %cd%:/backup alpine tar czf /backup/qdrant_data.tar.gz -C /data .
docker run --rm -v ragprogramm_hf_cache:/data -v %cd%:/backup alpine tar czf /backup/hf_cache.tar.gz -C /data .
docker run --rm -v ragprogramm_fastembed_cache:/data -v %cd%:/backup alpine tar czf /backup/fastembed_cache.tar.gz -C /data .
```

(`hf_cache`/`fastembed_cache` — веса TEI-моделей и кэш ONNX-моделей FastEmbed (`rag-service`/
`rag-worker`); оба необязательны — без них на новом устройстве модели просто скачаются/соберутся
заново при первом старте, займёт время, но не сломает ничего.)

Перенести получившиеся `.tar.gz` на новое устройство.

**На новом устройстве** — сначала один раз поднять и сразу погасить стек, чтобы Docker создал
пустые volume'ы с нужными именами, потом распаковать в них архивы:

```bash
docker compose -f docker-compose.full.yml up -d
docker compose -f docker-compose.full.yml down

docker run --rm -v ragprogramm_postgres_data:/data -v %cd%:/backup alpine sh -c "cd /data && tar xzf /backup/postgres_data.tar.gz"
docker run --rm -v ragprogramm_minio_data:/data -v %cd%:/backup alpine sh -c "cd /data && tar xzf /backup/minio_data.tar.gz"
docker run --rm -v ragprogramm_qdrant_data:/data -v %cd%:/backup alpine sh -c "cd /data && tar xzf /backup/qdrant_data.tar.gz"
docker run --rm -v ragprogramm_hf_cache:/data -v %cd%:/backup alpine sh -c "cd /data && tar xzf /backup/hf_cache.tar.gz"
docker run --rm -v ragprogramm_fastembed_cache:/data -v %cd%:/backup alpine sh -c "cd /data && tar xzf /backup/fastembed_cache.tar.gz"
```

Если нужен просто чистый старт без старых данных — пропусти весь этот шаг.

## 6. Собрать и запустить

```bash
docker compose -f docker-compose.full.yml up -d --build
```

Первая сборка — долгая (`rag-worker` тянет CUDA-образ + модели Docling, ~18 ГБ). Дальше
пересборка не нужна: `backend`/`rag_service`/`llm_service` смонтированы volume'ом, правки кода
подхватываются через `docker compose restart <service>`.

## 7. Миграции (только если стартуешь с пустой БД, шаг 5 пропущен)

```bash
alembic -n users upgrade head
alembic -n rag upgrade head
```

Если данные восстановлены из бэкапа (шаг 5) — этот шаг не нужен, схема уже внутри
`postgres_data`.

## 8. Проверить, что всё живо

```bash
docker compose -f docker-compose.full.yml ps
```

Все сервисы должны быть `running`/`healthy`. Открыть `http://localhost:8080` — должен
загрузиться фронтенд.

## 9. Поднять туннель к публичному домену

Для повседневного запуска — просто `start_local_full.bat` (в корне репозитория): сам поднимет
стек, проверит Docker/ключ/статус контейнеров и запустит туннель к `my-rag-project.ru`. Если
нужен только туннель отдельно (стек уже поднят) — `run_rag_tunnel.bat`.
