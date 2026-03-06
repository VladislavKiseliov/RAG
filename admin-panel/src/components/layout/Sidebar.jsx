import { LayoutDashboard, FileText, Users, ListChecks, Activity, ChevronsLeft, ChevronsRight, LogOut } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useUiStore } from '../../stores/uiStore';
import { useAuthStore } from '../../stores/authStore';

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/documents', label: 'Документы', icon: FileText, badge: 'documentsErrorCount' },
  { to: '/users', label: 'Пользователи', icon: Users },
  { to: '/tasks', label: 'Задачи', icon: ListChecks, badge: 'activeTasksCount' },
  { to: '/system-status', label: 'Статус системы', icon: Activity },
];

export default function Sidebar({ badges = {} }) {
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const setCollapsed = useUiStore((s) => s.setSidebarCollapsed);
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  return (
    <aside className={`sticky top-0 h-screen border-r border-slate-200 bg-primary text-slate-100 transition-all ${collapsed ? 'w-16' : 'w-60'}`}>
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between p-4">
          {!collapsed && <div className="text-lg font-semibold">RAG Admin</div>}
          <button className="rounded p-1 hover:bg-white/10" onClick={() => setCollapsed(!collapsed)}>
            {collapsed ? <ChevronsRight size={18} /> : <ChevronsLeft size={18} />}
          </button>
        </div>
        <nav className="flex-1 space-y-1 px-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const badge = item.badge ? badges[item.badge] : null;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center justify-between rounded-md px-3 py-2 text-sm ${isActive ? 'bg-accent text-white' : 'text-slate-200 hover:bg-white/10'}`
                }
              >
                <span className="flex items-center gap-2">
                  <Icon size={16} />
                  {!collapsed && item.label}
                </span>
                {!collapsed && badge > 0 && <span className="rounded-full bg-white/20 px-2 py-0.5 text-xs">{badge}</span>}
              </NavLink>
            );
          })}
        </nav>
        <div className="border-t border-white/20 p-3">
          {!collapsed && (
            <div className="mb-2 text-xs text-slate-300">
              <div className="font-medium text-slate-100">{user?.displayName || 'Admin'}</div>
              <div>{user?.username || 'admin'}</div>
            </div>
          )}
          <button className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-slate-200 hover:bg-white/10" onClick={logout}>
            <LogOut size={16} />
            {!collapsed && 'Выйти'}
          </button>
        </div>
      </div>
    </aside>
  );
}
