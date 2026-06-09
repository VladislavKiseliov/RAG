import { BASE_API_URL } from '../config/api';

export const createApiClient = (getAccessToken) => {
    const request = async (url, options = {}) => {
        const token = await getAccessToken();
        if (!token) throw new Error('Сессия истекла. Войдите снова.');

        const response = await fetch(BASE_API_URL + url, {
            ...options,
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
                ...options.headers,
            },
        });

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.detail || `Ошибка ${response.status}`);
        }

        return response.json();
    };

    return {
        get: (url) => request(url),
        post: (url, body) => request(url, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined }),
        patch: (url, body) => request(url, { method: 'PATCH', body: JSON.stringify(body) }),
        delete: (url) => request(url, { method: 'DELETE' }),
    };
};