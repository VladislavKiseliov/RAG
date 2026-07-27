import { BASE_API_URL } from '../config/api';

export const createApiClient = (getAccessToken) => {
    const request = async (url, options = {}) => {
        const token = await getAccessToken();
        if (!token) throw new Error('Сессия истекла. Войдите снова.');

        const isFormData = options.body instanceof FormData;

        const response = await fetch(BASE_API_URL + url, {
            ...options,
            headers: {
                'Authorization': `Bearer ${token}`,
                ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
                ...options.headers,
            },
        });

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.detail || `Ошибка ${response.status}`);
        }

        return response.json();
    };

    // Для SSE-эндпоинтов: не ждём/не парсим тело как JSON, отдаём сам ReadableStream
    // вызывающему коду (см. useAiChat.js).
    const requestStream = async (url, body) => {
        const token = await getAccessToken();
        if (!token) throw new Error('Сессия истекла. Войдите снова.');

        const response = await fetch(BASE_API_URL + url, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.detail || `Ошибка ${response.status}`);
        }

        return response.body;
    };

    return {
        get: (url, options) => request(url, options),
        post: (url, body) => request(url, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined }),
        postForm: (url, formData) => request(url, { method: 'POST', body: formData }),
        postStream: (url, body) => requestStream(url, body),
        patch: (url, body) => request(url, { method: 'PATCH', body: JSON.stringify(body) }),
        delete: (url) => request(url, { method: 'DELETE' }),
    };
};