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
        const chat = await api.post(ENDPOINTS.MESSENGER_DIRECT, { friend_guid: friendGuid });
        setChats((prev) => [chat, ...prev]);
        openChat(String(chat.chat_guid));
        return chat;
    }, [api, openChat]);

    const deleteChat = useCallback(async (chatGuid) => {
        await api.delete(ENDPOINTS.MESSENGER_CHAT(chatGuid));
        setChats((prev) => prev.filter((c) => String(c.chat_guid) !== chatGuid));
        if (String(activeChatGuid) === chatGuid) setActiveChatGuid(null);
    }, [api, activeChatGuid]);

    // WS event handlers
    const handleWsMessage = useCallback((data) => {
        switch (data.type) {
            case 'new': {
                setMessages((prev) => {
                    const existing = prev[data.chat_guid] ?? [];
                    return { ...prev, [data.chat_guid]: [...existing, data] };
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
                            m.guid === data.message_guid ? { ...m, is_read: true } : m
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
        handleWsMessage,
    };
}