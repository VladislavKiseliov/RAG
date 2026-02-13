// src/components/MessageInput.js

import React, { useState, useRef, useEffect } from 'react';

function MessageInput({ onSendMessage }) {
    const [message, setMessage] = useState('');
    const textareaRef = useRef(null);

    // Автоматическая подстройка высоты
    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = `${textarea.scrollHeight}px`;
        }
    }, [message]);

    const handleSubmit = (e) => {
        e.preventDefault();
        const trimmedMessage = message.trim();
        if (trimmedMessage) {
            onSendMessage(trimmedMessage);
            setMessage('');
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    };

    return (
        <div className="chat-input-container">
            <textarea
                id="messageInput"
                ref={textareaRef}
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
