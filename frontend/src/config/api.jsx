// src/config/api.js

// Базовый адрес FastAPI
// Используйте 127.0.0.1, если запускаете бэкенд локально на порту 8000
export const BASE_API_URL = "http://127.0.0.1:8000";

// Конкретные пути к эндпоинтам
export const ENDPOINTS = {
    LOGIN: "/auth/login",
    MESSAGES: (conversationId) => `/api/conversations/${conversationId}/messages`,
    CONVERSATIONS: "/api/conversations",
};