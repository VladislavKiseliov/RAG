import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import { useEffect, useState } from 'react';
import { getDocumentStats, getStats } from '../../api/adminApi';

export default function PageLayout() {
  const [badges, setBadges] = useState({ documentsErrorCount: 0, activeTasksCount: 0 });

  useEffect(() => {
    async function load() {
      const [stats, docStats] = await Promise.all([getStats(), getDocumentStats()]);
      setBadges({
        documentsErrorCount: docStats.error,
        activeTasksCount: stats.tasks_active,
      });
    }
    load();
  }, []);

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar badges={badges} />
      <main className="min-w-0 flex-1">
        <Topbar />
        <div className="p-5">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
