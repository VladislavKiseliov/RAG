import { useEffect, useRef, useCallback } from 'react';
import { ENDPOINTS } from '../config/api';

export function useMessengerSocket({ getAccessToken, onMessage, enabled = true }) {
    const wsRef = useRef(null);
    const reconnectTimer = useRef(null);
    const backoffRef = useRef(1000);
    const onMessageRef = useRef(onMessage);
    useEffect(() => { onMessageRef.current = onMessage; }, [onMessage]);

    // Outbox - только для new_message (реальных сообщений пользователя). typing/message_read
    // намеренно не очередятся - это одноразовые события, повторять их после реконнекта не нужно
    // (устаревшая typing-метка или пропущенный read-receipt не несут смысла спустя время).
    const outboxRef = useRef([]);

    const flushOutbox = useCallback(() => {
        const ws = wsRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        const pending = outboxRef.current;
        outboxRef.current = [];
        pending.forEach((payload) => ws.send(JSON.stringify(payload)));
    }, []);

    const connect = useCallback(async () => {
        const token = await getAccessToken?.();
        if (!token || !enabled) return;

        wsRef.current?.close();
        const ws = new WebSocket(ENDPOINTS.MESSENGER_WS());
        wsRef.current = ws;

        ws.onopen = () => {
            backoffRef.current = 1000;
            // Токен больше не в URL (утекал в access-логи nginx) - первое сообщение
            // после подключения обязано быть auth, иначе backend закрывает сокет.
            ws.send(JSON.stringify({ type: 'auth', token }));
            flushOutbox();
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                onMessageRef.current?.(data);
            } catch {
                // ignore malformed messages
            }
        };

        ws.onclose = () => {
            if (wsRef.current !== ws || !enabled) return;
            reconnectTimer.current = setTimeout(() => {
                backoffRef.current = Math.min(backoffRef.current * 2, 30000);
                connect();
            }, backoffRef.current);
        };

        ws.onerror = () => ws.close();
    }, [getAccessToken, enabled, flushOutbox]);

    useEffect(() => {
        if (enabled) connect();
        return () => {
            clearTimeout(reconnectTimer.current);
            wsRef.current?.close();
        };
    }, [enabled, connect]);

    const send = useCallback((payload) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(payload));
        }
    }, []);

    const sendMessage = useCallback((chatGuid, content, clientMsgId) => {
        const payload = { type: 'new_message', chat_guid: chatGuid, content, client_msg_id: clientMsgId };
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            send(payload);
        } else {
            // Сокет переподключается - складываем в очередь, flushOutbox отправит при onopen.
            outboxRef.current.push(payload);
        }
    }, [send]);

    const sendTyping = useCallback((chatGuid, userGuid) => {
        send({ type: 'user_typing', chat_guid: chatGuid, user_guid: userGuid });
    }, [send]);

    const markRead = useCallback((chatGuid, messageGuid) => {
        send({ type: 'message_read', chat_guid: chatGuid, message_guid: messageGuid });
    }, [send]);

    return { sendMessage, sendTyping, markRead };
}