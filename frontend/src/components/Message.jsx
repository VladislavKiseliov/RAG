// src/components/Message.js
import React from 'react';

function Message({ content, role }) {
    const className = role === 'user' ? 'user-message' : 'assistant-message';

    return (
        <div className={`message ${className}`}>
            <span>{content}</span>
        </div>
    );
}

export default Message;