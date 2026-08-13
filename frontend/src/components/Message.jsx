// src/components/Message.jsx
import React, { useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { useApi } from '../context/ApiContext';
import { ENDPOINTS } from '../config/api';

function TypingIndicator({ label }) {
    return (
        <div className="message assistant-message">
            <div className="message-bubble typing-bubble">
                {label && <span className="typing-label">{label}</span>}
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
            </div>
        </div>
    );
}

function HighlightedText({ text, childChunks }) {
    const parts = useMemo(() => {
        if (!childChunks || childChunks.length === 0) return [{ text, highlight: false }];
        const result = [];
        const positions = childChunks
            .map((chunk) => {
                const probe = chunk.slice(0, 60).trim();
                const idx = text.indexOf(probe);
                return idx !== -1 ? { start: idx, end: idx + chunk.length } : null;
            })
            .filter(Boolean)
            .sort((a, b) => a.start - b.start);
        let cursor = 0;
        for (const { start, end } of positions) {
            if (start > cursor) result.push({ text: text.slice(cursor, start), highlight: false });
            result.push({ text: text.slice(start, Math.min(end, text.length)), highlight: true });
            cursor = Math.min(end, text.length);
        }
        if (cursor < text.length) result.push({ text: text.slice(cursor), highlight: false });
        return result;
    }, [text, childChunks]);

    return (
        <>
            {parts.map((part, i) =>
                part.highlight
                    ? <mark key={i} className="source-highlight">{part.text}</mark>
                    : <span key={i}>{part.text}</span>
            )}
        </>
    );
}

function SourcesBlock({ sources }) {
    const api = useApi();
    const [expanded, setExpanded] = useState(false);
    const [openKeys, setOpenKeys] = useState(() => new Set());
    const [chunkState, setChunkState] = useState({}); // key -> { text, loading }
    // Текст источника из истории приходит без `text` (см. ChatService._strip_source_previews) —
    // подгружаем лениво по клику и кэшируем на время жизни компонента, чтобы повторное
    // открытие того же источника не било в сеть заново.
    const textCacheRef = useRef(new Map()); // parent_id -> text

    if (!sources || sources.length === 0) return null;

    const unique = [];
    const seen = new Set();
    for (const s of sources) {
        const key = s.parent_id ?? JSON.stringify(s);
        if (!seen.has(key)) {
            seen.add(key);
            unique.push(s);
        }
    }

    const formatName = (s) => {
        const h = s.headers || {};
        // headers приходят с ключами title/chapter_number (title уже содержит номер
        // главы впереди, напр. "2 Нормативные ссылки") — не H1..H4, которых там нет.
        const docName = s.source ? s.source.replace(/\.(pdf|docx?|txt)$/i, '').trim() : null;
        const chapter = h.title ? h.title.replace(/\*\*/g, '').trim() : null;
        const parts = [docName, chapter].filter(Boolean);
        if (parts.length > 0) return parts.join(' — ');
        return `Фрагмент ${unique.indexOf(s) + 1}`;
    };

    const loadChunk = (s, key) => {
        if (s.text) {
            setChunkState((prev) => ({ ...prev, [key]: { text: s.text, loading: false } }));
            return;
        }

        const cached = textCacheRef.current.get(key);
        if (cached != null) {
            setChunkState((prev) => ({ ...prev, [key]: { text: cached, loading: false } }));
            return;
        }

        setChunkState((prev) => ({ ...prev, [key]: { text: '', loading: true } }));
        api.get(ENDPOINTS.CHAT_SOURCE_CHUNK(key))
            .then((data) => {
                textCacheRef.current.set(key, data.text);
                setChunkState((prev) => ({ ...prev, [key]: { text: data.text, loading: false } }));
            })
            .catch(() => {
                setChunkState((prev) => ({ ...prev, [key]: { text: 'Не удалось загрузить текст источника.', loading: false } }));
            });
    };

    const toggleSource = (s, key) => {
        setOpenKeys((prev) => {
            const next = new Set(prev);
            if (next.has(key)) {
                next.delete(key);
            } else {
                next.add(key);
                if (!chunkState[key]) loadChunk(s, key);
            }
            return next;
        });
    };

    return (
        <div className="sources-block">
            <button className="sources-toggle" onClick={() => setExpanded((v) => !v)}>
                <span className="sources-icon">📄</span>
                <span>
                    {unique.length} {unique.length === 1 ? 'источник' : unique.length < 5 ? 'источника' : 'источников'}
                </span>
                <span className={`sources-chevron ${expanded ? 'open' : ''}`}>›</span>
            </button>
            {expanded && (
                <ul className="sources-list">
                    {unique.map((s, i) => {
                        const score = s.score != null ? Math.round(s.score * 100) : null;
                        const key = s.parent_id ?? JSON.stringify(s);
                        const canExpand = Boolean(s.text || s.parent_id);
                        const isOpen = canExpand && openKeys.has(key);
                        const state = chunkState[key];
                        return (
                            <li key={i} className="source-item-wrap">
                                <div
                                    className={`source-item ${canExpand ? 'source-item-clickable' : ''} ${isOpen ? 'source-item-open' : ''}`}
                                    onClick={canExpand ? () => toggleSource(s, key) : undefined}
                                >
                                    <span className="source-index">{i + 1}</span>
                                    <div className="source-info">
                                        <span className="source-name">{formatName(s)}</span>
                                        {score != null && (
                                            <span className="source-score"> · {score}%</span>
                                        )}
                                    </div>
                                    {canExpand && (
                                        <span className={`source-chunk-toggle ${isOpen ? 'open' : ''}`}>▸</span>
                                    )}
                                </div>
                                {isOpen && (
                                    <div className="source-chunk">
                                        {!state || state.loading
                                            ? 'Загрузка…'
                                            : <HighlightedText text={state.text} childChunks={s.child_chunks || []} />}
                                    </div>
                                )}
                            </li>
                        );
                    })}
                </ul>
            )}
        </div>
    );
}

function Message({ content, role, sources, isTyping, typingLabel, senderName, pending }) {
    if (isTyping) return <TypingIndicator label={typingLabel} />;

    const isUser = role === 'user';

    return (
        <div className={`message ${isUser ? 'user-message' : 'assistant-message'} ${pending ? 'message-pending' : ''}`}>
            {!isUser && (
                <div className="avatar assistant-avatar">
                    {senderName ? (
                        <span style={{ fontSize: '12px', fontWeight: 600 }}>
                            {senderName[0].toUpperCase()}
                        </span>
                    ) : (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                    )}
                </div>
            )}
            <div className="message-content-wrap">
                {senderName && (
                    <span className="message-sender-name">{senderName}</span>
                )}
                <div className="message-bubble">
                    {isUser || senderName ? (
                        <span className="message-text">{content}</span>
                    ) : (
                        <div className="message-markdown">
                            <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{content}</ReactMarkdown>
                        </div>
                    )}
                </div>
                {!isUser && !senderName && <SourcesBlock sources={sources} />}
            </div>
            {isUser && (
                <div className="avatar user-avatar">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z"/>
                    </svg>
                </div>
            )}
        </div>
    );
}

export { TypingIndicator };
export default Message;
