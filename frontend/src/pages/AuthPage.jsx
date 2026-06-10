import React, { useState } from 'react';
import { BASE_API_URL, ENDPOINTS } from '../config/api';

function AuthPage({ onLoginSuccess }) {
    const [isRegistering, setIsRegistering] = useState(false);
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [passwordConfirm, setPasswordConfirm] = useState('');
    const [error, setError] = useState(null);
    const [isLoading, setIsLoading] = useState(false);

    const switchMode = () => {
        setIsRegistering(!isRegistering);
        setError(null);
        setPassword('');
        setPasswordConfirm('');
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setIsLoading(true);

        try {
            if (isRegistering) {
                const res = await fetch(BASE_API_URL + ENDPOINTS.REGISTER, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username,
                        password,
                        password_confirm: passwordConfirm,
                    }),
                });
                const data = await res.json();

                if (res.ok) {
                    setIsRegistering(false);
                    setError(null);
                    setPassword('');
                    setPasswordConfirm('');
                } else {
                    const detail = data.detail;
                    if (Array.isArray(detail)) {
                        setError(detail.map(d => d.msg).join('. '));
                    } else {
                        setError(detail || `Ошибка регистрации (${res.status})`);
                    }
                }
            } else {
                const res = await fetch(BASE_API_URL + ENDPOINTS.LOGIN, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password }),
                });
                const data = await res.json();

                if (res.ok && data.access_token && data.refresh_token) {
                    localStorage.setItem('accessToken', data.access_token);
                    localStorage.setItem('refreshToken', data.refresh_token);
                    onLoginSuccess({
                        accessToken: data.access_token,
                        refreshToken: data.refresh_token,
                    });
                } else {
                    setError(data.detail || `Ошибка входа (${res.status})`);
                }
            }
        } catch {
            setError('Нет соединения с сервером. Проверьте подключение.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="auth-container">
            <div className="auth-box">
                <h2>{isRegistering ? 'Регистрация' : 'Вход'} в RAG Chat Pro</h2>
                <form onSubmit={handleSubmit}>
                    {error && <p className="auth-error">{error}</p>}

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
                    {isRegistering && (
                        <input
                            type="password"
                            placeholder="Повторите пароль"
                            value={passwordConfirm}
                            onChange={(e) => setPasswordConfirm(e.target.value)}
                            required
                        />
                    )}
                    <button type="submit" disabled={isLoading}>
                        {isLoading
                            ? 'Загрузка...'
                            : isRegistering ? 'Зарегистрироваться' : 'Войти'}
                    </button>
                </form>
                <button className="toggle-auth" onClick={switchMode}>
                    {isRegistering ? 'Уже есть аккаунт? Войти' : 'Нет аккаунта? Зарегистрироваться'}
                </button>
            </div>
        </div>
    );
}

export default AuthPage;