import React, { useEffect } from 'react';
import { useAdmin } from '../hooks/useAdmin';
import SystemStatusTab from '../components/admin/SystemStatusTab.jsx';
import DocumentsTab from '../components/admin/DocumentsTab.jsx';
import UsersTab from '../components/admin/UsersTab.jsx';
import StatsTab from '../components/admin/StatsTab.jsx';

const TABS = [
    { id: 'system', label: 'Статус системы' },
    { id: 'docs', label: 'Документы' },
    { id: 'users', label: 'Пользователи' },
    { id: 'stats', label: 'Статистика' },
];

function AdminPage({ api, showError }) {
    const admin = useAdmin(api, showError);

    useEffect(() => {
        admin.loadAll();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (
        <main className="adm-main">
            <header className="adm-header">
                <div>
                    <div className="adm-header-title">Админ-панель</div>
                    <div className="adm-header-sub">Системный мониторинг, документы и пользователи</div>
                </div>
                <div className={`adm-refresh${admin.loading ? ' spinning' : ''}`} onClick={admin.loadAll} title="Обновить">↻</div>
            </header>

            <nav className="adm-tabs">
                {TABS.map((t) => (
                    <button
                        key={t.id}
                        className={admin.tab === t.id ? 'active' : ''}
                        onClick={() => admin.setTab(t.id)}
                    >
                        {t.label}
                    </button>
                ))}
            </nav>

            <div className="adm-content">
                {admin.tab === 'system' && <SystemStatusTab health={admin.health} qdrant={admin.qdrant} tasks={admin.tasks} />}
                {admin.tab === 'docs' && <DocumentsTab admin={admin} />}
                {admin.tab === 'users' && <UsersTab admin={admin} />}
                {admin.tab === 'stats' && <StatsTab admin={admin} />}
            </div>
        </main>
    );
}

export default AdminPage;