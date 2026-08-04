import React, { useEffect, useRef, useState } from 'react';
import Message from './Message.jsx';
import MessageInput from './MessageInput.jsx';
import { useAiChat } from '../hooks/useAiChat';
import { useApi, useShowError } from '../context/ApiContext';
import { ENDPOINTS } from '../config/api';

// Докнутая панель чата с ассистентом — эфемерная по умолчанию (свежий useAiChat
// при каждом монтировании, история не переживает закрытие панели), с эскалацией
// в реальные Заметки/экспорт .txt после первого сообщения. Переиспользуется в
// Базе знаний (DocumentReader) и в Проектах (overview/document) — title передаёт
// контекст (название документа/проекта), не настоящий scoped RAG.
function AssistantChatPanel({ title, onClose }) {
    const api = useApi();
    const showError = useShowError();
    const aiChat = useAiChat(api, showError);
    const [savedFlash, setSavedFlash] = useState('');
    const messagesEndRef = useRef(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [aiChat.messages, aiChat.isTyping]);

    const hasMessages = aiChat.messages.length > 1; // messages[0] всегда GREETING

    const threadPlainText = () => {
        const header = `Диалог с ассистентом: ${title}\n${new Date().toLocaleString('ru-RU')}\n\n`;
        return header + aiChat.messages.map((m) => `${m.role === 'user' ? 'Вы' : 'Ассистент'}: ${m.content}`).join('\n\n');
    };

    const handleSend = (text) => {
        aiChat.sendAiMessage(`Вопрос по документу "${title}": ${text}`, aiChat.currentConversationId);
    };

    const handleSaveToNotes = async () => {
        try {
            await api.post(ENDPOINTS.NOTES, {
                title: `Диалог: ${title}`,
                content: threadPlainText(),
                folder: 'work',
                tags: [],
                pinned: false,
                reminder: null,
                follow_up: false,
            });
            setSavedFlash('Сохранено в Заметки ✓');
            setTimeout(() => setSavedFlash(''), 2400);
        } catch (e) {
            showError(e.message);
        }
    };

    const handleExportTxt = () => {
        const text = threadPlainText();
        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `диалог — ${title.replace(/[\\/:*?"<>|]/g, '')}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 2000);
    };

    return (
        <div className="assistant-chat-panel">
            <div className="assistant-chat-header">
                <div className="assistant-chat-header-row">
                    <span className="assistant-chat-title">✦ Ассистент</span>
                    <span className="assistant-chat-ephemeral-pill">не сохраняется</span>
                    <span className="assistant-chat-close" onClick={onClose}>✕</span>
                </div>
                <div className="assistant-chat-context clamp1">{title}</div>
            </div>

            <div className="assistant-chat-messages">
                {aiChat.messages.map((msg) => (
                    <Message key={msg.id} content={msg.content} role={msg.role} sources={msg.sources} />
                ))}
                {aiChat.isTyping && <Message isTyping typingLabel={aiChat.typingLabel} />}
                <div ref={messagesEndRef} />
            </div>

            {hasMessages && (
                <div className="assistant-chat-actions">
                    <div className="assistant-chat-action-btn" onClick={handleSaveToNotes}>📋 Сохранить в заметки</div>
                    <div className="assistant-chat-action-btn" onClick={handleExportTxt}>⭳ Экспорт .txt</div>
                </div>
            )}
            {savedFlash && <div className="assistant-chat-flash">{savedFlash}</div>}

            <MessageInput onSendMessage={handleSend} disabled={aiChat.isStreaming} />
        </div>
    );
}

export default AssistantChatPanel;
