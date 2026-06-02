// src/config/api.js

// Базовый адрес FastAPI
// Используйте 127.0.0.1, если запускаете бэкенд локально на порту 8000
export const BASE_API_URL = "http://127.0.0.1:8000";

// Конкретные пути к эндпоинтам
export const ENDPOINTS = {
    LOGIN: "/auth/login",
    REGISTER: "/auth/register",
    REFRESH: "/auth/refresh",
    LOGOUT: "/auth/logout",
    MESSAGES: (chatId) => `/api/chats/${chatId}/messages`,
    CONVERSATIONS: "/api/chats",
    PROFILE: "/api/profile",
};
