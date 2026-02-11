// src/pages/AuthPage.jsx

import React, { useState } from 'react';
import { BASE_API_URL, ENDPOINTS } from '../config/api'; // <-- Импорт констант

// Компонент-заглушка для экрана входа/регистрации
function AuthPage({ onLoginSuccess }) {
    const [isRegistering, setIsRegistering] = useState(false);
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState(null); // <-- НОВОЕ: Для отображения ошибок
    const [isLoading, setIsLoading] = useState(false); // <-- НОВОЕ: Для кнопки

    const handleSubmit = async (e) => { // <-- Сделаем функцию АСИНХРОННОЙ
        e.preventDefault();
        setError(null);
        setIsLoading(true);

        // 1. Собираем полный URL для LOGIN
        const API_URL = BASE_API_URL + ENDPOINTS.LOGIN;

        // Пока обрабатываем только вход, игнорируем регистрацию для простоты
        if (isRegistering) {
            setError("Функционал регистрации пока не реализован.");
            setIsLoading(false);
            return;
        }

        try {
            const response = await fetch(API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                // 2. Отправляем данные в формате JSON, как ждет FastAPI
                body: JSON.stringify({
                    username: username,
                    password: password,
                }),
            });

            const data = await response.json();

            if (response.ok && data.access_token && data.refresh_token) {
                // 3. Успех: сохраняем токен и переключаем страницу
                localStorage.setItem('accessToken', data.access_token);
                localStorage.setItem('refreshToken', data.refresh_token);
                onLoginSuccess({
                    accessToken: data.access_token,
                    refreshToken: data.refresh_token,
                });
            } else {
                // 4. Ошибка (например, 401 Unauthorized от FastAPI)
                // data.detail содержит сообщение об ошибке, отправленное FastAPI
                const errorMessage = data.detail || `Login failed with status: ${response.status}`;
                console.error("Login error:", errorMessage);
                setError(errorMessage);
            }

        } catch (fetchError) {
            console.error("Network error when connecting to API:", fetchError);
            setError("Network error when connecting to server. Please check your connection and ensure the backend is running.");
        } finally {
            setIsLoading(false); // Снимаем состояние загрузки в любом случае
        }
    };

    return (
        <div className="auth-container">
            <div className="auth-box">
                <h2>{isRegistering ? 'Регистрация' : 'Вход'} в RAG Chat Pro</h2>
                <form onSubmit={handleSubmit}>
                    {/* НОВОЕ: Вывод сообщения об ошибке */}
                    {error && <p style={{ color: 'red', fontWeight: 'bold' }}>{error}</p>}

                    <input
                        type="text"
                        placeholder="Имя пользователя"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        required
                    />
                    <input
                        type="password"
                        placeholder="Пароль"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                    />
                    <button type="submit" disabled={isLoading}>
                        {isLoading
                            ? 'Загрузка...'
                            : (isRegistering ? 'Зарегистрироваться' : 'Войти')}
                    </button>
                </form>
                <button
                    className="toggle-auth"
                    onClick={() => setIsRegistering(!isRegistering)}
                >
                    {isRegistering ? 'Уже есть аккаунт? Войти' : 'Нет аккаунта? Зарегистрироваться'}
                </button>
            </div>
        </div>
    );
}

export default AuthPage;
