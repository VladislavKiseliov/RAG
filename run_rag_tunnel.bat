@echo off
:loop
echo [%date% %time%] Запуск безопасного туннеля к RAG-проекту...
ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=3 -o StreamLocalBindUnlink=yes -i "C:\Users\rgg1\Downloads\privatekey-1083073.pem" -N -R 8080:127.0.0.1:8080 -R 8081:127.0.0.1:8081 ubuntu@195.209.218.96
echo [%date% %time%] Соединение потеряно. Переподключение через 5 секунд...
timeout /t 5
goto loop