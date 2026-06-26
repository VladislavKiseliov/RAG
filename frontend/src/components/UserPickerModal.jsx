import React, { useState, useEffect, useRef } from 'react';
import { ENDPOINTS } from '../config/api';
import { formatUserName, formatUserInitial } from '../utils/formatUserName';
import { TIMEOUTS } from '../config/constants';
import { useApi } from '../context/ApiContext';

function UserPickerModal({ onSelect, onClose }) {
    const api = useApi();
    const [query, setQuery] = useState('');
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(false);
    const debounceTimer = useRef(null);

    useEffect(() => {
        clearTimeout(debounceTimer.current);
        debounceTimer.current = setTimeout(async () => {
            if (!query.trim()) {
                setUsers([]);
                return;
            }
            setLoading(true);
            try {
                const data = await api.get(ENDPOINTS.USERS_SEARCH(query));
                setUsers(data);
            } catch {
                setUsers([]);
            } finally {
                setLoading(false);
            }
        }, TIMEOUTS.SEARCH_DEBOUNCE);
        return () => clearTimeout(debounceTimer.current);
    }, [query, api]);

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
                    {!loading && users.length === 0 && (
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