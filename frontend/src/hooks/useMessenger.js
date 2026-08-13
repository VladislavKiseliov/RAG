import { useState, useCallback, useRef } from 'react';
import { ENDPOINTS } from '../config/api';
import { TIMEOUTS } from '../config/constants';

export function useMessenger(api, showError) {
    const [chats, setChats] = useState([]);
    const [activeChatGuid, setActiveChatGuid] = useState(null);
    const [messages, setMessages] = useState({});
    const [typingUsers, setTypingUsers] = useState({});
    const typingTimers = useRef({});

    const loadChats = useCallback(async () => {
        try {
            const data = await api.get(ENDPOINTS.MESSENGER_CHATS);
            setChats(data);
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError]);

    const loadMessages = useCallback(async (chatGuid) => {
        try {
            const data = await api.get(ENDPOINTS.MESSENGER_MESSAGES(chatGuid));
            setMessages((prev) => ({ ...prev, [chatGuid]: data }));
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError]);

    const openChat = useCallback((chatGuid) => {
        setActiveChatGuid(chatGuid);
        if (chatGuid && !messages[chatGuid]) loadMessages(chatGuid);
    }, [messages, loadMessages]);

    const createDirectChat = useCallback(async (friendGuid) => {
        try {
            const chat = await api.post(ENDPOINTS.MESSENGER_DIRECT, { friend_guid: friendGuid });
            setChats((prev) => [chat, ...prev]);
            openChat(String(chat.chat_guid));
            return chat;
        } catch (e) {
            showError(e.message);
            return null;
        }
    }, [api, showError, openChat]);

    const deleteChat = useCallback(async (chatGuid) => {
        try {
            await api.delete(ENDPOINTS.MESSENGER_CHAT(chatGuid));
            setChats((prev) => prev.filter((c) => String(c.chat_guid) !== chatGuid));
            if (String(activeChatGuid) === chatGuid) setActiveChatGuid(null);
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError, activeChatGuid]);

    // Optimistic UI: показываем сообщение сразу после отправки, не дожидаясь ответа сервера.
    // Подтверждение (case 'new' ниже) находит эту запись по client_msg_id и заменяет её на
    // реальную - той же клавишей client_msg_id, чтобы React не перерисовывал элемент заново.
    //
    // Эхо "new" может не долететь обратно этому же клиенту (обрыв WS на нестабильном
    // соединении, напр. через SSH-туннель) - сообщение при этом уже сохранено на сервере,
    // просто подтверждение потерялось. Без recovery запись осталась бы pending навсегда.
    // pendingTimersRef на таймауте перечитывает чат через REST (источник истины) - если
    // сообщение и правда сохранилось, оно появится в ответе; если реально не дошло - тоже
    // корректно отражается (просто не появится), лучше, чем вечный "тёмный" призрак.
    const pendingTimersRef = useRef({});

    const addPendingMessage = useCallback((chatGuid, { clientMsgId, content, userGuid }) => {
        setMessages((prev) => {
            const existing = prev[chatGuid] ?? [];
            return {
                ...prev,
                [chatGuid]: [...existing, {
                    client_msg_id: clientMsgId,
                    content,
                    user_guid: userGuid,
                    created_at: new Date().toISOString(),
                    pending: true,
                }],
            };
        });

        pendingTimersRef.current[clientMsgId] = setTimeout(() => {
            delete pendingTimersRef.current[clientMsgId];
            setMessages((prev) => {
                const stillPending = (prev[chatGuid] ?? []).some(
                    (m) => m.pending && m.client_msg_id === clientMsgId
                );
                if (stillPending) loadMessages(chatGuid);
                return prev;
            });
        }, TIMEOUTS.MESSAGE_PENDING_RECONCILE);
    }, [loadMessages]);

    // WS event handlers
    const handleWsMessage = useCallback((data) => {
        switch (data.type) {
            case 'new': {
                if (data.client_msg_id && pendingTimersRef.current[data.client_msg_id]) {
                    clearTimeout(pendingTimersRef.current[data.client_msg_id]);
                    delete pendingTimersRef.current[data.client_msg_id];
                }
                setMessages((prev) => {
                    const existing = prev[data.chat_guid] ?? [];
                    // Подтверждение своего же optimistic-сообщения (см. addPendingMessage) -
                    // заменяем pending-запись подтверждённой, а не добавляем дубль.
                    const pendingIdx = data.client_msg_id
                        ? existing.findIndex((m) => m.pending && m.client_msg_id === data.client_msg_id)
                        : -1;
                    const next = pendingIdx === -1
                        ? [...existing, data]
                        : existing.map((m, i) => (i === pendingIdx ? data : m));
                    return { ...prev, [data.chat_guid]: next };
                });
                setChats((prev) => prev.map((c) =>
                    c.chat_guid === data.chat_guid
                        ? { ...c, last_message_content: data.content, updated_at: data.created_at }
                        : c
                ));
                break;
            }
            case 'new_chat_created': {
                setChats((prev) => {
                    const guid = String(data.chat_guid);
                    if (prev.some(c => String(c.chat_guid) === guid)) return prev;
                    return [data, ...prev];
                });
                break;
            }
            case 'message_read': {
                setMessages((prev) => {
                    const chatMsgs = prev[data.chat_guid];
                    if (!chatMsgs) return prev;
                    return {
                        ...prev,
                        [data.chat_guid]: chatMsgs.map((m) =>
                            (m.guid ?? m.message_guid) === data.last_read_message_guid ? { ...m, is_read: true } : m
                        ),
                    };
                });
                break;
            }
            case 'user_typing': {
                const key = `${data.chat_guid}:${data.user_guid}`;
                clearTimeout(typingTimers.current[key]);
                setTypingUsers((prev) => ({
                    ...prev,
                    [data.chat_guid]: new Set([...(prev[data.chat_guid] ?? []), data.user_guid]),
                }));
                typingTimers.current[key] = setTimeout(() => {
                    setTypingUsers((prev) => {
                        const next = new Set(prev[data.chat_guid] ?? []);
                        next.delete(data.user_guid);
                        return { ...prev, [data.chat_guid]: next };
                    });
                }, TIMEOUTS.TYPING_INDICATOR);
                break;
            }
            case 'chat_deleted': {
                const deletedGuid = String(data.chat_guid);
                setChats((prev) => prev.filter((c) => String(c.chat_guid) !== deletedGuid));
                if (activeChatGuid === deletedGuid) setActiveChatGuid(null);
                break;
            }
        }
    }, [activeChatGuid]);

    return {
        chats,
        activeChatGuid,
        messages,
        typingUsers,
        loadChats,
        openChat,
        createDirectChat,
        deleteChat,
        addPendingMessage,
        handleWsMessage,
    };
}