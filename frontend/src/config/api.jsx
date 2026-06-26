export const BASE_API_URL = import.meta.env.VITE_API_URL || "";

export const ENDPOINTS = {
    LOGIN: "/auth/login",
    REGISTER: "/auth/register",
    REFRESH: "/auth/refresh",
    LOGOUT: "/auth/logout",
    PROFILE: "/api/profile",
    CONVERSATIONS: "/api/chats",
    MESSAGES: (chatId) => `/api/chats/${chatId}/messages`,
    USERS_SEARCH: (q) => `/api/users/search?q=${encodeURIComponent(q)}`,
    MESSENGER_CHATS: "/messenger/chats/",
    MESSENGER_DIRECT: "/messenger/chats/direct",
    MESSENGER_CHAT: (guid) => `/messenger/chats/${guid}`,
    MESSENGER_MESSAGES: (guid) => `/messenger/chats/${guid}/messages`,
    MESSENGER_WS: (token) => {
        const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
        return `${proto}://${window.location.host}/websocket/ws/?token=${token}`;
    },
};