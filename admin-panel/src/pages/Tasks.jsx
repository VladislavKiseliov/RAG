import { useCallback, useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Badge from '../components/ui/Badge';
import TableSkeleton from '../components/ui/TableSkeleton';
import Modal from '../components/ui/Modal';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import { cancelTask, getTasks } from '../api/adminApi';
import { shortId } from '../utils/formatters';
import { TASK_TABS } from '../utils/constants';
import { useUiStore } from '../stores/uiStore';

export default function Tasks() {
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [tab, setTab] = useState('active');
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, pages: 1 });
  const [traceback, setTraceback] = useState(null);
  const [cancelTarget, setCancelTarget] = useState(null);
  const refreshTick = useUiStore((s) => s.refreshTick);
  const setLastUpdatedAt = useUiStore((s) => s.setLastUpdatedAt);

  const load = useCallback(async (page = 1, options = { silent: false }) => {
    if (options.silent) setIsRefreshing(true);
    else setLoading(true);

    try {
      const res = await getTasks(tab, page);
      setRows(res.items);
      setMeta({ page: res.page, pages: res.pages });
      setLastUpdatedAt(new Date().toISOString());
    } finally {
      if (options.silent) setIsRefreshing(false);
      else setLoading(false);
    }
  }, [tab, setLastUpdatedAt]);

  useEffect(() => {
    load(1, { silent: false });
  }, [tab, refreshTick, load]);

  const onCancel = async () => {
    await cancelTask(cancelTarget.task_id);
    toast.success('Задача отменена');
    setCancelTarget(null);
    await load(meta.page, { silent: true });
  };

  return (
    <Card
      title="Задачи Celery"
      right={(
        <div className="flex items-center gap-2">
          {isRefreshing && <span className="text-xs text-muted">Обновление...</span>}
          <Button variant="secondary" onClick={() => load(meta.page, { silent: false })}>Обновить</Button>
        </div>
      )}
    >
      <div className="mb-3 flex gap-2">
        {TASK_TABS.map((x) => (
          <button
            key={x}
            className={`rounded-md px-3 py-1 text-sm ${tab === x ? 'bg-accent text-white' : 'bg-slate-100 text-text'}`}
            onClick={() => setTab(x)}
          >
            {x}
          </button>
        ))}
      </div>
      {loading ? (
        <TableSkeleton rows={8} cols={5} />
      ) : (
        <div className="overflow-auto">
          <table className="table-sticky min-w-full text-sm">
            <thead>
              <tr className="bg-slate-100 text-left">
                <th className="p-2">Task ID</th>
                <th className="p-2">Файл</th>
                <th className="p-2">Статус</th>
                <th className="p-2">Время</th>
                <th className="p-2">Действие</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.task_id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="mono p-2">{shortId(row.task_id)}</td>
                  <td className="p-2">{row.filename}</td>
                  <td className="p-2"><Badge value={row.status} /></td>
                  <td className="p-2">{row.elapsed}</td>
                  <td className="p-2">
                    {row.status === 'FAILURE' && <button className="text-accent hover:underline" onClick={() => setTraceback(row.traceback)}>Детали</button>}
                    {row.status === 'ACTIVE' && <button className="text-danger hover:underline" onClick={() => setCancelTarget(row)}>Отменить</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="mt-3 flex items-center justify-between">
        <Button variant="secondary" disabled={meta.page <= 1} onClick={() => load(meta.page - 1, { silent: false })}>Предыдущая</Button>
        <span className="text-sm text-muted">Страница {meta.page} из {meta.pages}</span>
        <Button variant="secondary" disabled={meta.page >= meta.pages} onClick={() => load(meta.page + 1, { silent: false })}>Следующая</Button>
      </div>

      <Modal open={Boolean(traceback)} onClose={() => setTraceback(null)} title="Traceback">
        <pre className="max-h-80 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">{traceback}</pre>
      </Modal>
      <ConfirmDialog
        open={Boolean(cancelTarget)}
        onClose={() => setCancelTarget(null)}
        onConfirm={onCancel}
        title="Отменить задачу"
        description={`Task: ${cancelTarget?.task_id || ''}`}
        confirmText="Отменить"
        danger
      />
    </Card>
  );
}
