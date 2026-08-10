import React, { useState, useEffect, useRef } from 'react';
import { ENDPOINTS } from '../config/api';
import { formatUserName, formatUserInitial } from '../utils/formatUserName';
import { TIMEOUTS } from '../config/constants';
import { useApi, useShowError } from '../context/ApiContext';

function UserPickerModal({ onSelect, onClose }) {
    const api = useApi();
    const showError = useShowError();
    const [query, setQuery] = useState('');
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(false);
    const [searchFailed, setSearchFailed] = useState(false);
    const debounceTimer = useRef(null);
    // Если предыдущий запрос ещё летит, когда пришёл ответ на новый — без этой проверки
    // более медленный старый ответ может перезаписать актуальные результаты (race condition).
    const latestQueryRef = useRef('');

    useEffect(() => {
        clearTimeout(debounceTimer.current);
        debounceTimer.current = setTimeout(async () => {
            const q = query.trim();
            if (!q) {
                setUsers([]);
                setSearchFailed(false);
                return;
            }
            latestQueryRef.current = q;
            setLoading(true);
            try {
                const data = await api.get(ENDPOINTS.USERS_SEARCH(q));
                if (latestQueryRef.current !== q) return;
                setUsers(data);
                setSearchFailed(false);
            } catch (e) {
                if (latestQueryRef.current !== q) return;
                setUsers([]);
                setSearchFailed(true);
                showError(e.message);
            } finally {
                if (latestQueryRef.current === q) setLoading(false);
            }
        }, TIMEOUTS.SEARCH_DEBOUNCE);
        return () => clearTimeout(debounceTimer.current);
    }, [query, api, showError]);

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <span>Новый чат</span>
                    <button className="icon-btn" onClick={onClose}>✕</button>
                </div>
                <input
                    className="modal-search"
                    placeholder="Поиск по имени..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    autoFocus
                />
                <div className="modal-user-list">
                    {loading && <div className="modal-hint">Поиск...</div>}
                    {!loading && searchFailed && (
                        <div className="modal-hint">Не удалось выполнить поиск</div>
                    )}
                    {!loading && !searchFailed && users.length === 0 && (
                        <div className="modal-hint">Пользователи не найдены</div>
                    )}
                    {users.map((user) => (
                        <button
                            key={user.guid}
                            className="modal-user-item"
                            onClick={() => onSelect(user.guid)}
                        >
                            <span className="user-avatar">{formatUserInitial(user)}</span>
                            <span className="user-name">{formatUserName(user)}</span>
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
}

export default UserPickerModal;