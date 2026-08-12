@echo off
chcp 1251 >nul
cls

echo ========================================================
echo     Запуск локального окружения RAG-проекта (Full)
echo ========================================================
echo.

REM --- 0. Проверка и автозапуск Docker Desktop ---
echo [0/3] Проверка статуса Docker Engine...
docker info >nul 2>&1
if errorlevel 1 (
    echo [ИНФО] Docker Engine не запущен. Запускаем Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"

    echo Ожидание полной инициализации Docker Engine...
    :wait_docker
    timeout /t 3 /nobreak >nul
    docker info >nul 2>&1
    if errorlevel 1 (
        echo Ожидание...
        goto wait_docker
    )
    echo [OK] Docker Engine успешно запущен и готов к работе!
    echo.
) else (
    echo [OK] Docker Engine уже работает.
    echo.
)

REM --- 1. Поднимаем Docker-контейнеры ---
echo [1/3] Запуск Docker Compose...
docker compose -f docker-compose.full.yml up -d --remove-orphans
if errorlevel 1 (
    echo.
    echo [ВНИМАНИЕ] Первая попытка запуска не удалась. Повторный запуск через 3 секунды...
    timeout /t 3 /nobreak >nul
    docker compose -f docker-compose.full.yml up -d --remove-orphans
)

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Не удалось запустить Docker Compose!
    echo Пожалуйста, проверьте статус Docker Desktop вручную.
    pause
    exit /b 1
)

echo.
echo [OK] Все контейнеры успешно запущены!
echo.

REM --- 2. Поднимаем мониторинг (Grafana/Prometheus/Loki) ---
echo [2/3] Запуск мониторинга (Grafana/Prometheus/Loki)...
docker compose -f Monitoring/docker-compose.yml up -d
if errorlevel 1 (
    echo [ВНИМАНИЕ] Мониторинг не поднялся — не критично, стек и туннель продолжат работу без него.
) else (
    echo [OK] Мониторинг поднят: Grafana http://localhost:3000, Prometheus http://localhost:9090.
)
echo.

REM --- 3. Поднимаем SSH-туннель в фоновом режиме ---
echo [3/3] Запуск SSH-туннеля к VPS (195.209.218.96)...
echo.

:start_tunnel
echo [%date% %time%] Подключение туннеля...

REM Запускаем SSH в фоновом процессе
start "RAG_SSH_TUNNEL" /B ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=3 -o StreamLocalBindUnlink=yes -i "C:\Users\rgg1\Downloads\privatekey-1083073.pem" -N -R 8080:127.0.0.1:8080 -R 8081:127.0.0.1:8081 ubuntu@195.209.218.96 >nul 2>&1

REM Ждем 3 секунды для установления соединения
timeout /t 3 /nobreak >nul

REM Проверяем, запущен ли процесс ssh.exe
tasklist /FI "IMAGENAME eq ssh.exe" 2>NUL | find /I /N "ssh.exe">NUL
if errorlevel 1 (
    echo [%date% %time%] [ОШИБКА] Не удалось установить SSH-соединение!
    goto reconnect
)

REM Повторно форсируем кодировку перед выводом плашки
chcp 1251 >nul
echo.
echo ========================================================
echo  [OK] ВСЕ СЕРВИСЫ УСПЕШНО ЗАПУЩЕНЫ!
echo  [OK] SSH-туннель успешно подключен.
echo.
echo  Не закрывайте это окно. Для остановки просто закройте его.
echo ========================================================
echo.

:wait_loop
timeout /t 5 /nobreak >nul
tasklist /FI "IMAGENAME eq ssh.exe" 2>NUL | find /I /N "ssh.exe">NUL
if errorlevel 1 goto reconnect
goto wait_loop

:reconnect
echo.
echo [%date% %time%] [ВНИМАНИЕ] Соединение с туннелем потеряно. Переподключение через 5 секунд...
timeout /t 5 /nobreak >nul
goto start_tunnel