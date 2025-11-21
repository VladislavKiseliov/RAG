// src/App.jsx

import React, { useState } from 'react';
import ChatPage from './pages/ChatPage.jsx';
import AuthPage from './pages/AuthPage.jsx'; // <-- Новый импорт!

function App() {
    // Состояние, определяющее, вошел ли пользователь в систему
    const [isLoggedIn, setIsLoggedIn] = useState(false);

    const handleLoginSuccess = () => {
        setIsLoggedIn(true);
    };

    // Условный рендеринг: показываем либо чат, либо страницу авторизации
    return (
        isLoggedIn
            ? <ChatPage />
            : <AuthPage onLoginSuccess={handleLoginSuccess} />
    );
}

export default App;