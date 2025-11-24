// src/App.jsx

import React, { useState } from 'react';
import ChatPage from './pages/ChatPage.jsx';
import AuthPage from './pages/AuthPage.jsx'; // <-- Новый импорт!

function App() {
    // Состояние, определяющее, вошел ли пользователь в систему
    const [isLoggedIn, setIsLoggedIn] = useState(false);
    const [accessToken, setAccessToken] = useState(null); // <-- Добавлено: состояние для токена

     const handleLoginSuccess = (token) => { // <-- Обновлено: принимаем токен
        setAccessToken(token); // <-- Сохраняем токен
        setIsLoggedIn(true);
    };

    // Условный рендеринг: показываем либо чат, либо страницу авторизации
    return (
        isLoggedIn
            ? <ChatPage accessToken={accessToken} />
            : <AuthPage onLoginSuccess={handleLoginSuccess} />
    );
}

export default App;