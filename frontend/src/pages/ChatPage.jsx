import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useNavigate, useLocation, useMatch } from 'react-router-dom';
import MessageInput from '../components/MessageInput.jsx';
import Sidebar from '../components/Sidebar.jsx';
import Message from '../components/Message.jsx';
import AppRail from '../components/AppRail.jsx';
import HomePage from './HomePage.jsx';
import KnowledgeBasePage from './KnowledgeBasePage.jsx';
import ProjectsPage from './ProjectsPage.jsx';
import NotesPage from './NotesPage.jsx';
import TasksPage from './TasksPage.jsx';
import AdminPage from './AdminPage.jsx';
import { createApiClient } from '../api/client';
import { useAiChat } from '../hooks/useAiChat';
import { useMessenger } from '../hooks/useMessenger';
import { useMessengerSocket } from '../hooks/useMessengerSocket';
import { useErrorToast } from '../hooks/useErrorToast';
import { useCurrentUser } from '../hooks/useCurrentUser';
import { formatUserName } from '../utils/formatUserName';
import { ApiContext } from '../context/ApiContext';

function ChatPage({ accessToken, currentUserGuid, getAccessToken, onLogout, theme, onToggleTheme }) {
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const messagesEndRef = useRef(null);

    // Раздел и id открытого AI-чата живут в URL (не в useState) - чтобы обновление
    // страницы (F5) возвращало туда же, а не сбрасывало на Главную.
    const navigate = useNavigate();
    const location = useLocation();
    const chatMatch = useMatch('/chats/:conversationId');
    const conversationId = chatMatch?.params.conversationId ?? null;
    const section = location.pathname === '/' ? 'home'
        : location.pathname.startsWith('/chats') ? 'chats'
        : location.pathname.startsWith('/knowledge') ? 'knowledge'
        : location.pathname.startsWith('/projects') ? 'projects'
        : location.pathname.startsWith('/notes') ? 'notes'
        : location.pathname.startsWith('/tasks') ? 'tasks'
        : location.pathname.startsWith('/admin') ? 'admin'
        : 'home';
    const goToSection = useCallback((id) => navigate(id === 'home' ? '/' : `/${id}`), [navigate]);

    const api = useMemo(() => createApiClient(getAccessToken), [getAccessToken]);
    const { error, showError } = useErrorToast();
    const aiChat = useAiChat(api, showError);
    const messenger = useMessenger(api, showError);
    const currentUser = useCurrentUser(api, showError);
    const isAdmin = currentUser.isAdmin;

    // Единая точка входа для событий из сокета — каждый подписчик сам узнаёт по data.type,
    // что ему нужно, и игнорирует остальное (messenger.handleWsMessage так уже делает).
    // Сюда же добавлять будущие обработчики (например, для note.indexed/document.indexed),
    // не раздувая handleWsMessage чужой для messenger доменной логикой.
    const handleSocketMessage = useCallback((data) => {
        messenger.handleWsMessage(data);
    }, [messenger.handleWsMessage]);

    const { sendMessage: wsSendMessage, sendTyping, markRead } = useMessengerSocket({
        getAccessToken,
        onMessage: handleSocketMessage,
        enabled: !!accessToken,
    });

    useEffect(() => {
        if (accessToken) {
            aiChat.loadUserConversations();
            messenger.loadChats();
        }
    }, [accessToken]);

    // URL -> состояние: id открытого AI-чата приходит из :conversationId, а не наоборот -
    // так refresh/прямая ссылка/кнопка "назад" всегда попадают в тот же диалог.
    useEffect(() => {
        aiChat.setCurrentConversationId(conversationId);
    }, [conversationId]);

    // Обратное направление - только для случая, когда sendAiMessage сам создаёт новый чат
    // (id ещё не было в URL). Остальные переходы уже делают navigate() сами (selectAiChat).
    useEffect(() => {
        if (aiChat.currentConversationId && aiChat.currentConversationId !== conversationId) {
            navigate(`/chats/${aiChat.currentConversationId}`, { replace: true });
        }
    }, [aiChat.currentConversationId]);

    useEffect(() => {
        if (aiChat.currentConversationId) {
            aiChat.loadConversationHistory(aiChat.currentConversationId);
        } else {
            aiChat.resetMessages();
        }
        return aiChat.abortHistory;
    }, [aiChat.currentConversationId]);

    const activeMessengerMessages = messenger.messages[messenger.activeChatGuid];

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [aiChat.messages, aiChat.isTyping, activeMessengerMessages]);

    const handleSendMessage = useCallback(async (text) => {
        if (messenger.activeChatGuid) {
            const clientMsgId = crypto.randomUUID();
            messenger.addPendingMessage(messenger.activeChatGuid, {
                clientMsgId, content: text, userGuid: currentUserGuid,
            });
            wsSendMessage(messenger.activeChatGuid, text, clientMsgId);
            return;
        }
        await aiChat.sendAiMessage(text, aiChat.currentConversationId);
    }, [
        messenger.activeChatGuid, messenger.addPendingMessage, wsSendMessage, currentUserGuid,
        aiChat.sendAiMessage, aiChat.currentConversationId,
    ]);

    const selectAiChat = useCallback((id) => {
        messenger.openChat(null);
        navigate(id ? `/chats/${id}` : '/chats');
    }, [messenger.openChat, navigate]);

    const selectMessengerChat = useCallback((guid) => {
        messenger.openChat(guid);
        aiChat.setCurrentConversationId(null);
        navigate('/chats');
    }, [messenger.openChat, aiChat.setCurrentConversationId, navigate]);

    const messengerMessages = useMemo(() => activeMessengerMessages ?? [], [activeMessengerMessages]);
    const activeChat = messenger.chats.find(c => String(c.chat_guid) === messenger.activeChatGuid);
    const friendName = formatUserName(activeChat);
    const isMessengerMode = !!messenger.activeChatGuid;
    const activeConversation = aiChat.conversations.find(c => c.chat_guid === aiChat.currentConversationId);
    const othersTyping = isMessengerMode
        && [...(messenger.typingUsers[messenger.activeChatGuid] ?? [])].some((g) => g !== currentUserGuid);

    // Отмечаем последнее сообщение прочитанным при открытии чата и при приходе новых сообщений,
    // пока чат открыт. Серверное эхо message_read (в т.ч. себе же) пересоздаёт messengerMessages,
    // из-за чего этот эффект без guard'а перезапускался бы на собственное эхо бесконечно и заливал
    // WS rate-limit (см. B2 в ISSUES.md) — lastMarkedReadRef пропускает повтор для уже
    // отмеченного guid, а не полагается на идемпотентность backend upsert.
    const lastMarkedReadRef = useRef({});
    useEffect(() => {
        if (!isMessengerMode || messengerMessages.length === 0) return;
        const last = messengerMessages[messengerMessages.length - 1];
        const lastGuid = last.guid ?? last.message_guid;
        if (!lastGuid) return;
        const chatGuid = messenger.activeChatGuid;
        if (lastMarkedReadRef.current[chatGuid] === lastGuid) return;
        lastMarkedReadRef.current[chatGuid] = lastGuid;
        markRead(chatGuid, lastGuid);
    }, [isMessengerMode, messengerMessages, messenger.activeChatGuid, markRead]);

    const chatHeader = isMessengerMode
        ? { icon: (friendName[0] ?? '?').toUpperCase(), title: friendName || 'Чат', sub: 'Личные сообщения', iconStyle: 'dm' }
        : aiChat.currentConversationId
            ? { icon: null, title: activeConversation?.title || 'AI-чат', sub: 'AI-ассистент', iconStyle: 'ai' }
            : null;

    return (
        <ApiContext.Provider value={{ api, showError }}>
            <div className="app-shell">
                {error && (
                    <div className="error-toast">
                        <span>⚠ {error}</span>
                    </div>
                )}
                <AppRail
                    activeSection={section}
                    onSelectSection={goToSection}
                    theme={theme}
                    onToggleTheme={onToggleTheme}
                    isAdmin={isAdmin}
                    onLogout={onLogout}
                    currentUser={currentUser}
                />

                {section === 'chats' && (
                    <div className="app-layout">
                        <Sidebar
                            currentConversationId={aiChat.currentConversationId}
                            setCurrentConversationId={selectAiChat}
                            conversations={aiChat.conversations}
                            loadUserConversations={aiChat.loadUserConversations}
                            onConversationRemoved={aiChat.removeConversation}
                            onConversationRenamed={aiChat.renameConversation}
                            messengerChats={messenger.chats}
                            activeChatGuid={messenger.activeChatGuid}
                            onSelectMessengerChat={selectMessengerChat}
                            onCreateDirectChat={messenger.createDirectChat}
                            onDeleteMessengerChat={messenger.deleteChat}
                            onToggleSidebar={() => setSidebarCollapsed((v) => !v)}
                            isCollapsed={sidebarCollapsed}
                            onOpenProjects={() => goToSection('projects')}
                        />
                        <main className="main-chat">
                            {chatHeader && (
                                <header className="chat-header">
                                    <div className={`chat-header-icon ${chatHeader.iconStyle}`}>
                                        {chatHeader.iconStyle === 'ai' ? (
                                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                                                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                            </svg>
                                        ) : chatHeader.icon}
                                    </div>
                                    <div>
                                        <div className="chat-header-title">{chatHeader.title}</div>
                                        <div className="chat-header-sub">{chatHeader.sub}</div>
                                    </div>
                                </header>
                            )}
                            <div className="chat-container">
                                <div className="chat-history" id="chatHistory">
                                    {isMessengerMode ? (
                                        messengerMessages.length === 0
                                            ? <div className="chat-list-item empty">Нет сообщений</div>
                                            : messengerMessages.map((msg) => {
                                                const isOwn = String(msg.user_guid) === currentUserGuid;
                                                return (
                                                    <Message
                                                        key={msg.guid ?? msg.message_guid ?? msg.client_msg_id}
                                                        content={msg.content}
                                                        role={isOwn ? 'user' : 'assistant'}
                                                        senderName={isOwn ? undefined : friendName}
                                                        pending={msg.pending}
                                                    />
                                                );
                                            })
                                    ) : (
                                        aiChat.messages.map((msg) => (
                                            <Message
                                                key={msg.id}
                                                content={msg.content}
                                                role={msg.role}
                                                sources={msg.sources}
                                            />
                                        ))
                                    )}
                                    {aiChat.isTyping && !isMessengerMode && <Message isTyping typingLabel={aiChat.typingLabel} />}
                                    {othersTyping && <Message isTyping />}
                                    <div ref={messagesEndRef} />
                                </div>
                                <MessageInput
                                    onSendMessage={handleSendMessage}
                                    disabled={aiChat.isStreaming && !isMessengerMode}
                                    onTyping={isMessengerMode ? () => sendTyping(messenger.activeChatGuid, currentUserGuid) : undefined}
                                />
                            </div>
                        </main>
                    </div>
                )}

                {section === 'home' && <HomePage currentUser={currentUser} onSelectSection={goToSection} />}

                {section === 'knowledge' && <KnowledgeBasePage />}

                {section === 'projects' && <ProjectsPage />}

                {section === 'notes' && <NotesPage theme={theme} />}

                {section === 'tasks' && <TasksPage onSelectSection={goToSection} />}

                {section === 'admin' && isAdmin && <AdminPage />}
            </div>
        </ApiContext.Provider>
    );
}

export default ChatPage;