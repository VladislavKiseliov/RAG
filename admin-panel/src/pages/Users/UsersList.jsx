import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Card from '../../components/ui/Card';
import TableSkeleton from '../../components/ui/TableSkeleton';
import EmptyState from '../../components/ui/EmptyState';
import Badge from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import { getUsers } from '../../api/adminApi';
import { useDebounce } from '../../hooks/useDebounce';
import { PAGE_SIZES } from '../../utils/constants';
import { formatDateTime, initialsFromName } from '../../utils/formatters';
import { useUiStore } from '../../stores/uiStore';

export default function UsersList() {
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, pages: 1, total: 0 });
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [sortBy, setSortBy] = useState('registered_at');
  const [sortDir, setSortDir] = useState('desc');
  const debounced = useDebounce(search);
  const refreshTick = useUiStore((s) => s.refreshTick);
  const setLastUpdatedAt = useUiStore((s) => s.setLastUpdatedAt);

  const load = useCallback(async (page = 1) => {
    setLoading(true);
    const res = await getUsers({
      page,
      pageSize: PAGE_SIZES.users,
      search: debounced,
      status,
      sortBy,
      sortDir,
    });
    setRows(res.items);
    setMeta({ page: res.page, pages: res.pages, total: res.total });
    setLoading(false);
    setLastUpdatedAt(new Date().toISOString());
  }, [debounced, status, sortBy, sortDir, setLastUpdatedAt]);

  useEffect(() => {
    load(1);
  }, [load, refreshTick]);

  return (
    <Card title="Пользователи">
      <div className="mb-3 flex gap-2">
        <input className="rounded-md border border-slate-300 px-3 py-2 text-sm" placeholder="Поиск username..." value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="all">Все</option>
          <option value="active">Активен</option>
          <option value="blocked">Заблокирован</option>
        </select>
        <select className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
          <option value="registered_at">Дата регистрации</option>
          <option value="username">Имя</option>
          <option value="chats_count">Чаты</option>
        </select>
        <Button variant="secondary" onClick={() => setSortDir((v) => (v === 'asc' ? 'desc' : 'asc'))}>{sortDir}</Button>
      </div>
      {loading ? <TableSkeleton rows={8} cols={6} /> : rows.length === 0 ? <EmptyState title="Пользователей нет" description="Пустой результат фильтра." /> : (
        <div className="overflow-auto">
          <table className="table-sticky min-w-full text-sm">
            <thead>
              <tr className="bg-slate-100 text-left">
                <th className="p-2">Аватар</th>
                <th className="p-2">Имя</th>
                <th className="p-2">Чатов</th>
                <th className="p-2">Сообщ.</th>
                <th className="p-2">Дата рег.</th>
                <th className="p-2">Статус</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.user_id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="p-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/10 font-semibold text-accent">
                      {initialsFromName(row.username)}
                    </div>
                  </td>
                  <td className="p-2"><Link className="text-accent hover:underline" to={`/users/${row.user_id}`}>{row.username}</Link></td>
                  <td className="p-2">{row.chats_count}</td>
                  <td className="p-2">{row.messages_count}</td>
                  <td className="p-2">{formatDateTime(row.registered_at)}</td>
                  <td className="p-2"><Badge value={row.is_blocked ? 'blocked' : 'active'} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="mt-3 flex items-center justify-between">
        <Button variant="secondary" disabled={meta.page <= 1} onClick={() => load(meta.page - 1)}>Предыдущая</Button>
        <span className="text-sm text-muted">Страница {meta.page} из {meta.pages}</span>
        <Button variant="secondary" disabled={meta.page >= meta.pages} onClick={() => load(meta.page + 1)}>Следующая</Button>
      </div>
    </Card>
  );
}
