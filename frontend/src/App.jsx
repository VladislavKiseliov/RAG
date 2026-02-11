// src/App.jsx

import React, { useEffect, useRef, useState } from 'react';
import ChatPage from './pages/ChatPage.jsx';
import AuthPage from './pages/AuthPage.jsx'; // <-- Новый импорт!
import { BASE_API_URL, ENDPOINTS } from './config/api.jsx';

function App() {
    // Состояние, определяющее, вошел ли пользователь в систему
    const [isLoggedIn, setIsLoggedIn] = useState(false);
    const [accessToken, setAccessToken] = useState(null); // <-- Добавлено: состояние для токена
    const refreshPromiseRef = useRef(null);

    const setAuthTokens = (tokens) => {
        const access = tokens?.accessToken || null;
        const refresh = tokens?.refreshToken || null;

        setAccessToken(access);
        if (access && refresh) {
            localStorage.setItem('accessToken', access);
            localStorage.setItem('refreshToken', refresh);
            setIsLoggedIn(true);
        } else {
            localStorage.removeItem('accessToken');
            localStorage.removeItem('refreshToken');
            setIsLoggedIn(false);
        }
    };

    const handleLoginSuccess = (tokens) => { // <-- Обновлено: принимаем токены
        setAuthTokens(tokens);
    };

    useEffect(() => {
        const storedAccess = localStorage.getItem('accessToken');
        const storedRefresh = localStorage.getItem('refreshToken');
        if (storedAccess && storedRefresh) {
            setIsLoggedIn(true);
            setAccessToken(storedAccess);
        }
    }, []);

    const parseJwt = (token) => {
        try {
            const base64Url = token.split('.')[1];
            if (!base64Url) return null;
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            const jsonPayload = decodeURIComponent(
                atob(base64)
                    .split('')
                    .map((c) => `%${(`00${c.charCodeAt(0).toString(16)}`).slice(-2)}`)
                    .join('')
            );
            return JSON.parse(jsonPayload);
        } catch (error) {
            return null;
        }
    };

    const isTokenExpiring = (token, skewSeconds = 60) => {
        const payload = parseJwt(token);
        if (!payload || !payload.exp) return true;
        const expiryMs = payload.exp * 1000;
        return expiryMs - Date.now() < skewSeconds * 1000;
    };

    const refreshAccessToken = async (refreshToken) => {
        const response = await fetch(BASE_API_URL + ENDPOINTS.REFRESH, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ refresh_token: refreshToken }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.access_token || !data.refresh_token) {
            return null;
        }
        return {
            accessToken: data.access_token,
            refreshToken: data.refresh_token,
        };
    };

    const getAccessToken = async () => {
        let token = accessToken || localStorage.getItem('accessToken');
        const refreshToken = localStorage.getItem('refreshToken');
        if (!token || !refreshToken) return null;

        if (!isTokenExpiring(token)) {
            return token;
        }

        if (!refreshPromiseRef.current) {
            refreshPromiseRef.current = refreshAccessToken(refreshToken).finally(() => {
                refreshPromiseRef.current = null;
            });
        }

        const newTokens = await refreshPromiseRef.current;
        if (newTokens) {
            setAuthTokens(newTokens);
            return newTokens.accessToken;
        }

        setAuthTokens(null);
        return null;
    };

    const logout = async (revokeAll = false) => {
        const refreshToken = localStorage.getItem('refreshToken');
        if (refreshToken) {
            try {
                await fetch(BASE_API_URL + ENDPOINTS.LOGOUT, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ refresh_token: refreshToken, revoke_all: revokeAll }),
                });
            } catch (error) {
                // ignore network errors on logout
            }
        }
        setAuthTokens(null);
    };

    // Условный рендеринг: показываем либо чат, либо страницу авторизации
    return (
        isLoggedIn
            ? <ChatPage accessToken={accessToken} getAccessToken={getAccessToken} onLogout={logout} />
            : <AuthPage onLoginSuccess={handleLoginSuccess} />
    );
}

export default App;
