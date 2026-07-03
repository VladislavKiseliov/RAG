import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import MessageInput from '../components/MessageInput.jsx';
import Sidebar from '../components/Sidebar.jsx';
import Message from '../components/Message.jsx';
import AppRail from '../components/AppRail.jsx';
import KnowledgeBasePage from './KnowledgeBasePage.jsx';
import ProjectsPage from './ProjectsPage.jsx';
import { createApiClient } from '../api/client';
import { useAiChat } from '../hooks/useAiChat';
import { useMessenger } from '../hooks/useMessenger';
import { useMessengerSocket } from '../hooks/useMessengerSocket';
import { useErrorToast } from '../hooks/useErrorToast';
import { formatUserName } from '../utils/formatUserName';
import { ApiContext } from '../context/ApiContext';

function ChatPage({ accessToken, currentUserGuid, getAccessToken, onLogout, theme, onToggleTheme }) {
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const [section, setSection] = useState('chats');
    const messagesEndRef = useRef(null);

    const api = useMemo(() => createApiClient(getAccessToken), [getAccessToken]);
    const { error, showError } = useErrorToast();
    const aiChat = useAiChat(api, showError);
    const messenger = useMessenger(api);

    const { sendMessage: wsSendMessage } = useMessengerSocket({
        getAccessToken,
        onMessage: messenger.handleWsMessage,
        enabled: !!accessToken,
    });

    useEffect(() => {
        if (accessToken) {
            aiChat.loadUserConversations();
            messenger.loadChats();
        }
    }, [accessToken]);

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
            wsSendMessage(messenger.activeChatGuid, text);
            return;
        }
        await aiChat.sendAiMessage(text, aiChat.currentConversationId);
    }, [messenger.activeChatGuid, wsSendMessage, aiChat.sendAiMessage, aiChat.currentConversationId]);

    const selectAiChat = useCallback((id) => {
        aiChat.setCurrentConversationId(id);
        messenger.openChat(null);
    }, [aiChat.setCurrentConversationId, messenger.openChat]);

    const selectMessengerChat = useCallback((guid) => {
        messenger.openChat(guid);
        aiChat.setCurrentConversationId(null);
    }, [messenger.openChat, aiChat.setCurrentConversationId]);

    const messengerMessages = activeMessengerMessages ?? [];
    const activeChat = messenger.chats.find(c => String(c.chat_guid) === messenger.activeChatGuid);
    const friendName = formatUserName(activeChat);
    const isMessengerMode = !!messenger.activeChatGuid;
    const activeConversation = aiChat.conversations.find(c => c.chat_guid === aiChat.currentConversationId);

    const chatHeader = isMessengerMode
        ? { icon: (friendName[0] ?? '?').toUpperCase(), title: friendName || 'Чат', sub: 'Личные сообщения', iconStyle: 'dm' }
        : aiChat.currentConversationId
            ? { icon: null, title: activeConversation?.title || 'AI-чат', sub: 'AI-ассистент', iconStyle: 'ai' }
            : null;

    return (
        <ApiContext.Provider value={api}>
            <div className="app-shell">
                <AppRail
                    activeSection={section}
                    onSelectSection={setSection}
                    theme={theme}
                    onToggleTheme={onToggleTheme}
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
                            onLogout={onLogout}
                            theme={theme}
                            onToggleTheme={onToggleTheme}
                            onToggleSidebar={() => setSidebarCollapsed((v) => !v)}
                            isCollapsed={sidebarCollapsed}
                            onOpenProjects={() => setSection('projects')}
                        />
                        <main className="main-chat">
                            {error && (
                                <div className="error-toast">
                                    <span>⚠ {error}</span>
                                </div>
                            )}
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
                                                        key={msg.guid ?? msg.message_guid}
                                                        content={msg.content}
                                                        role={isOwn ? 'user' : 'assistant'}
                                                        senderName={isOwn ? undefined : friendName}
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
                                    {aiChat.isTyping && !isMessengerMode && <Message isTyping />}
                                    <div ref={messagesEndRef} />
                                </div>
                                <MessageInput
                                    onSendMessage={handleSendMessage}
                                    disabled={aiChat.isTyping && !isMessengerMode}
                                />
                            </div>
                        </main>
                    </div>
                )}

                {section === 'knowledge' && <KnowledgeBasePage api={api} showError={showError} />}

                {section === 'projects' && (
                    <ProjectsPage api={api} showError={showError} onOpenMessenger={() => setSection('chats')} />
                )}
            </div>
        </ApiContext.Provider>
    );
}

export default ChatPage;