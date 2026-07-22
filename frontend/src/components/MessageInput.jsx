// src/components/MessageInput.jsx
import React, { useState, useRef, useEffect } from 'react';

function MessageInput({ onSendMessage, disabled, onTyping }) {
    const [message, setMessage] = useState('');
    const textareaRef = useRef(null);
    const lastTypingRef = useRef(0);

    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
        }
    }, [message]);

    // Фокус после снятия блокировки
    useEffect(() => {
        if (!disabled) textareaRef.current?.focus();
    }, [disabled]);

    const handleSubmit = (e) => {
        e?.preventDefault();
        const trimmed = message.trim();
        if (trimmed && !disabled) {
            onSendMessage(trimmed);
            setMessage('');
        }
    };

    const handleChange = (e) => {
        setMessage(e.target.value);
        if (!onTyping) return;
        const now = Date.now();
        if (now - lastTypingRef.current > 2000) {
            lastTypingRef.current = now;
            onTyping();
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    };

    return (
        <div className="chat-input-container">
            <div className={`input-wrapper ${disabled ? 'input-disabled' : ''}`}>
                <textarea
                    ref={textareaRef}
                    placeholder={disabled ? 'Получаю ответ...' : 'Напишите сообщение...'}
                    rows="1"
                    value={message}
                    onChange={handleChange}
                    onKeyDown={handleKeyDown}
                    disabled={disabled}
                    autoFocus
                />
                <button
                    onClick={handleSubmit}
                    disabled={disabled || !message.trim()}
                    className="send-btn"
                    aria-label="Отправить"
                >
                    {disabled ? (
                        <span className="send-spinner" />
                    ) : (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                            <path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                    )}
                </button>
            </div>
            <p className="input-hint">Enter — отправить · Shift+Enter — новая строка</p>
        </div>
    );
}

export default MessageInput;