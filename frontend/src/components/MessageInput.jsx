// src/components/MessageInput.js

import React, { useState, useRef, useEffect } from 'react';

function MessageInput({ onSendMessage }) {
    const [message, setMessage] = useState('');
    const textareaRef = useRef(null);

    // Логика автоматической настройки высоты
    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = 'auto'; // Сброс
            textarea.style.height = `${textarea.scrollHeight}px`; // Установка нужной высоты
        }
    }, [message]); // Эффект срабатывает при каждом изменении сообщения (message)

    const handleSubmit = (e) => {
        e.preventDefault();
        const trimmedMessage = message.trim();
        if (trimmedMessage) {
            // Вызываем внешнюю функцию для отправки
            onSendMessage(trimmedMessage);
            setMessage(''); // Очищаем поле
        }
    };

    const handleKeyDown = (e) => {
        // Отправка по Enter, но не по Shift + Enter
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault(); // Предотвращаем стандартное поведение (перенос строки)
            handleSubmit(e);
        }
    };

    return (
        <div className="chat-input-container">
            {/* Связываем поле с состоянием через value и onChange */}
            <textarea
                id="messageInput"
                ref={textareaRef} // Привязываем useRef для доступа к DOM-элементу
                placeholder="Напишите сообщение..."
                rows="1"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                autoFocus
            />
            <button id="sendButton" onClick={handleSubmit}>
                <span>&#x27A4;</span>
            </button>
        </div>
    );
}

export default MessageInput;