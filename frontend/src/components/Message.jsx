// src/components/Message.jsx
import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function TypingIndicator() {
    return (
        <div className="message assistant-message">
            <div className="message-bubble typing-bubble">
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
            </div>
        </div>
    );
}

function SourcesBlock({ sources }) {
    const [expanded, setExpanded] = useState(false);
    const [tooltip, setTooltip] = useState(null); // { text, name, top, left, width }
    const tooltipRef = useRef(null);
    const closeTimerRef = useRef(null);

    useEffect(() => {
        return () => {
            if (closeTimerRef.current) {
                clearTimeout(closeTimerRef.current);
            }
        };
    }, []);

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

    const clearCloseTimer = () => {
        if (closeTimerRef.current) {
            clearTimeout(closeTimerRef.current);
            closeTimerRef.current = null;
        }
    };

    const scheduleCloseTooltip = () => {
        clearCloseTimer();
        closeTimerRef.current = setTimeout(() => {
            setTooltip(null);
            closeTimerRef.current = null;
        }, 180);
    };

    const formatName = (s) => {
        const h = s.headers || {};
        const parts = ['H1', 'H2', 'H3', 'H4']
            .map((k) => h[k])
            .filter(Boolean)
            .map((v) => v.replace(/\*\*/g, '').trim());
        if (parts.length > 0) return parts.join(' › ');
        return `Фрагмент ${unique.indexOf(s) + 1}`;
    };

    const highlightChunks = (parentText, childChunks) => {
        if (!childChunks || childChunks.length === 0) return [{ text: parentText, highlight: false }];

        const parts = [];
        let remaining = parentText;
        let offset = 0;

        // Сортируем child chunks по позиции в parent тексте
        const positions = childChunks
            .map((chunk) => {
                // Ищем по первым 60 символам chunk для устойчивости к нормализации
                const probe = chunk.slice(0, 60).trim();
                const idx = remaining.indexOf(probe, offset);
                return idx !== -1 ? { start: idx, end: idx + chunk.length, chunk } : null;
            })
            .filter(Boolean)
            .sort((a, b) => a.start - b.start);

        let cursor = 0;
        for (const { start, end } of positions) {
            if (start > cursor) parts.push({ text: parentText.slice(cursor, start), highlight: false });
            parts.push({ text: parentText.slice(start, Math.min(end, parentText.length)), highlight: true });
            cursor = Math.min(end, parentText.length);
        }
        if (cursor < parentText.length) parts.push({ text: parentText.slice(cursor), highlight: false });

        return parts;
    };

    const handleMouseEnter = (e, s) => {
        if (!s.text) return;
        clearCloseTimer();
        const rect = e.currentTarget.getBoundingClientRect();
        setTooltip({
            text: s.text,
            childChunks: s.child_chunks || [],
            name: formatName(s),
            top: rect.top + window.scrollY,
            left: rect.left + window.scrollX,
            width: rect.width,
        });
    };

    return (
        <>
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
                            return (
                                <li
                                    key={i}
                                    className="source-item"
                                    onMouseEnter={(e) => handleMouseEnter(e, s)}
                                    onMouseLeave={scheduleCloseTooltip}
                                >
                                    <span className="source-index">{i + 1}</span>
                                    <div className="source-info">
                                        <span className="source-name">{formatName(s)}</span>
                                        {score != null && (
                                            <span className="source-score"> · {score}%</span>
                                        )}
                                    </div>
                                    {s.text && (
                                        <span className="source-preview-hint" title="Наведи для просмотра">
                                            ⋯
                                        </span>
                                    )}
                                </li>
                            );
                        })}
                    </ul>
                )}
            </div>

            {tooltip && (
                <div
                    ref={tooltipRef}
                    className="source-tooltip"
                    style={{
                        position: 'fixed',
                        left: Math.min(tooltip.left, window.innerWidth - 420),
                        top: tooltip.top - 8,
                        transform: 'translateY(-100%)',
                        zIndex: 9999,
                        width: 400,
                        maxWidth: 'calc(100vw - 32px)',
                    }}
                    onMouseEnter={clearCloseTimer}
                    onMouseLeave={scheduleCloseTooltip}
                >
                    <div className="source-tooltip-header">{tooltip.name}</div>
                    <div className="source-tooltip-text">
                        {highlightChunks(tooltip.text, tooltip.childChunks).map((part, i) =>
                            part.highlight
                                ? <mark key={i} className="source-highlight">{part.text}</mark>
                                : <span key={i}>{part.text}</span>
                        )}
                    </div>
                </div>
            )}
        </>
    );
}

function Message({ content, role, sources, isTyping }) {
    if (isTyping) return <TypingIndicator />;

    const isUser = role === 'user';

    return (
        <div className={`message ${isUser ? 'user-message' : 'assistant-message'}`}>
            {!isUser && (
                <div className="avatar assistant-avatar">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                </div>
            )}
            <div className="message-content-wrap">
                <div className="message-bubble">
                    {isUser ? (
                        <span className="message-text">{content}</span>
                    ) : (
                        <div className="message-markdown">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                        </div>
                    )}
                </div>
                {!isUser && <SourcesBlock sources={sources} />}
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
