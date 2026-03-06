import { Bell, RefreshCw } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { useUiStore } from '../../stores/uiStore';
import { useNotificationsStore } from '../../stores/notificationsStore';
import Button from '../ui/Button';

dayjs.extend(relativeTime);

const labels = {
  '/dashboard': 'Dashboard',
  '/documents': 'Документы',
  '/users': 'Пользователи',
  '/tasks': 'Задачи',
  '/system-status': 'Статус системы',
  '/login': 'Вход',
};

export default function Topbar() {
  const location = useLocation();
  const requestRefresh = useUiStore((s) => s.requestRefresh);
  const lastUpdatedAt = useUiStore((s) => s.lastUpdatedAt);
  const notifications = useNotificationsStore((s) => s.items);

  const base = ['/', '/documents', '/users'].find((v) => location.pathname === v || location.pathname.startsWith(`${v}/`))
    || location.pathname;

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white px-5 py-3">
      <div>
        <p className="text-xs text-muted">Admin Panel</p>
        <h1 className="text-xl font-semibold text-text">{labels[base] || 'Раздел'}</h1>
      </div>
      <div className="flex items-center gap-2">
        <p className="text-xs text-muted">{lastUpdatedAt ? `Обновлено ${dayjs(lastUpdatedAt).fromNow()}` : 'Нет обновлений'}</p>
        <Button variant="secondary" onClick={requestRefresh}>
          <RefreshCw size={14} />
          Обновить
        </Button>
        <button className="relative rounded-md border border-slate-200 p-2">
          <Bell size={16} />
          {notifications.length > 0 && <span className="absolute -right-1 -top-1 rounded-full bg-danger px-1 text-[10px] text-white">{notifications.length}</span>}
        </button>
      </div>
    </header>
  );
}
