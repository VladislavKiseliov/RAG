import React from 'react';

function UsersTab({ admin }) {
    return (
        <table className="adm-table">
            <thead>
                <tr><th>Пользователь</th><th>Email</th><th>Роль</th><th>Документов</th><th>Активность</th><th>Статус</th></tr>
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
                    </tr>
                ))}
            </tbody>
        </table>
    );
}

export default UsersTab;