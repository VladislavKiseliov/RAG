import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PieChart, Pie, Cell, ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import TableSkeleton from '../components/ui/TableSkeleton';
import { formatRelative } from '../utils/formatters';
import { getDocumentStats, getLatestDocuments, getStats } from '../api/adminApi';
import { useUiStore } from '../stores/uiStore';

const colors = { completed: '#2D6A4F', processing: '#E9C46A', error: '#E76F51' };

function MetricCard({ title, value, delta, to }) {
  return (
    <Link to={to} className="rounded-xl border border-slate-200 bg-white p-4 transition hover:border-accent">
      <p className="text-sm text-muted">{title}</p>
      <p className="mt-2 text-3xl font-semibold">{value}</p>
      {delta !== undefined && <p className="text-sm text-success">{delta >= 0 ? `+${delta}` : delta} за 7д</p>}
    </Link>
  );
}

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [docStats, setDocStats] = useState(null);
  const [latestDocs, setLatestDocs] = useState([]);
  const refreshTick = useUiStore((s) => s.refreshTick);
  const setLastUpdatedAt = useUiStore((s) => s.setLastUpdatedAt);

  const load = useCallback(async () => {
    setLoading(true);
    const [statsRes, docStatsRes, latest] = await Promise.all([getStats(), getDocumentStats(), getLatestDocuments(10)]);
    setStats(statsRes);
    setDocStats(docStatsRes);
    setLatestDocs(latest);
    setLoading(false);
    setLastUpdatedAt(new Date().toISOString());
  }, [setLastUpdatedAt]);

  useEffect(() => {
    load();
  }, [load, refreshTick]);

  if (loading || !stats || !docStats) return <TableSkeleton rows={8} cols={4} />;

  const donutData = [
    { name: 'completed', value: docStats.completed },
    { name: 'processing', value: docStats.processing },
    { name: 'error', value: docStats.error },
  ];

  return (
    <div className="space-y-4">
      <section className="grid grid-cols-4 gap-4">
        <MetricCard title="Документы" value={stats.documents_total} delta={stats.documents_delta_7d} to="/documents" />
        <MetricCard title="Пользователи" value={stats.users_total} delta={stats.users_delta_7d} to="/users" />
        <MetricCard title="Чаты" value={stats.chats_total} delta={stats.chats_delta_7d} to="/users" />
        <MetricCard title="Активные задачи" value={stats.tasks_active} to="/tasks" />
      </section>
      <section className="grid grid-cols-2 gap-4">
        <Card title="Статусы документов">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={donutData} dataKey="value" innerRadius={70} outerRadius={95} paddingAngle={2}>
                  {donutData.map((entry) => <Cell key={entry.name} fill={colors[entry.name]} />)}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="grid grid-cols-3 gap-2 text-sm">
            {donutData.map((row) => (
              <div key={row.name} className="rounded border border-slate-200 p-2">
                <p>{row.name}</p>
                <p className="font-semibold">{row.value}</p>
              </div>
            ))}
          </div>
        </Card>
        <Card title="Активность 7 дней">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={stats.activity_7d}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="documents" stroke="#457B9D" strokeWidth={2} />
                <Line type="monotone" dataKey="messages" stroke="#1D3557" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </section>
      <Card title="Последние документы" right={<Link to="/documents" className="text-sm text-accent">Смотреть все</Link>}>
        <div className="overflow-auto">
          <table className="table-sticky min-w-full border-collapse text-sm">
            <thead>
              <tr className="bg-slate-100 text-left">
                <th className="p-2">Имя файла</th>
                <th className="p-2">Статус</th>
                <th className="p-2">Загружен</th>
                <th className="p-2">Действие</th>
              </tr>
            </thead>
            <tbody>
              {latestDocs.map((doc) => (
                <tr key={doc.doc_id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="p-2">{doc.filename}</td>
                  <td className="p-2"><Badge value={doc.status} /></td>
                  <td className="p-2">{formatRelative(doc.uploaded_at)}</td>
                  <td className="p-2">
                    {doc.status === 'error' ? <button className="text-danger hover:underline">Повторить</button> : <Link to={`/documents/${doc.doc_id}`} className="text-accent hover:underline">Детали</Link>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
