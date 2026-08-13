import React, { useState } from 'react';

function UsersTab({ admin }) {
    const [confirmDeleteId, setConfirmDeleteId] = useState(null);

    const handleDelete = (userId) => {
        setConfirmDeleteId(null);
        admin.deleteUser(userId);
    };

    return (
        <table className="adm-table">
            <thead>
                <tr><th>Пользователь</th><th>Email</th><th>Роль</th><th>Документов</th><th>Активность</th><th>Статус</th><th /></tr>
            </thead>
            <tbody>
                {admin.users.map((u) => (
                    <tr key={u.id}>
                        <td className="adm-user-cell">
                            <span className="adm-avatar">{(u.name?.[0] || '?').toUpperCase()}</span>
                            <span>{u.name}</span>
                        </td>
                        <td>{u.email}</td>
                        <td>
                            <span
                                className={`adm-role-pill${u.isAdmin ? ' admin' : ''}`}
                                onClick={() => admin.toggleUserRole(u.id, u.isAdmin)}
                            >
                                {u.isAdmin ? 'Админ' : 'Пользователь'}
                            </span>
                        </td>
                        <td className="mono">{u.docsCount ?? '—'}</td>
                        <td>{u.lastActiveLabel}</td>
                        <td>
                            <span
                                className={`status-pill ${u.active ? 'online' : 'offline'}`}
                                title="Демо: блокировка не сохраняется на сервере, эндпоинта пока нет"
                                onClick={() => admin.toggleUserActiveLocal(u.id)}
                            >
                                <span className="dot" />{u.active ? 'Активен' : 'Заблокирован'}
                            </span>
                        </td>
                        <td className="adm-row-actions">
                            {confirmDeleteId === u.id ? (
                                <>
                                    <span title="Подтвердить удаление" onClick={() => handleDelete(u.id)}>✓</span>
                                    <span title="Отмена" onClick={() => setConfirmDeleteId(null)}>✕</span>
                                </>
                            ) : (
                                <span title="Удалить пользователя" onClick={() => setConfirmDeleteId(u.id)}>🗑</span>
                            )}
                        </td>
                    </tr>
                ))}
            </tbody>
        </table>
    );
}

export default UsersTab;