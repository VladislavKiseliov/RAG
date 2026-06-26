import React, { useState, useEffect } from 'react';
import ChatPage from './pages/ChatPage.jsx';
import AuthPage from './pages/AuthPage.jsx';
import { useAuth } from './hooks/useAuth';

function App() {
    const { isLoggedIn, accessToken, currentUserGuid, getAccessToken, logout, setAuthTokens } = useAuth();
    const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');

    useEffect(() => {
        document.documentElement.dataset.theme = theme;
        localStorage.setItem('theme', theme);
    }, [theme]);

    const toggleTheme = () => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));

    return (
        isLoggedIn
            ? <ChatPage accessToken={accessToken} currentUserGuid={currentUserGuid} getAccessToken={getAccessToken} onLogout={logout} theme={theme} onToggleTheme={toggleTheme} />
            : <AuthPage onLoginSuccess={setAuthTokens} />
    );
}

export default App;