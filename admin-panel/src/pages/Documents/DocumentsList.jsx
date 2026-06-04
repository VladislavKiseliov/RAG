import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import Badge from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import TableSkeleton from '../../components/ui/TableSkeleton';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import { bulkDeleteDocuments, deleteDocument, getDocuments, reindexDocument, uploadDocuments } from '../../api/adminApi';
import { useDebounce } from '../../hooks/useDebounce';
import UploadModal from './UploadModal';
import { PAGE_SIZES } from '../../utils/constants';
import { formatDateTime } from '../../utils/formatters';
import { useUiStore } from '../../stores/uiStore';

export default function DocumentsList() {
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, pages: 1, total: 0 });
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [sortBy, setSortBy] = useState('uploaded_at');
  const [sortDir, setSortDir] = useState('desc');
  const [selected, setSelected] = useState([]);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const debouncedSearch = useDebounce(search, 300);
  const refreshTick = useUiStore((s) => s.refreshTick);
  const setLastUpdatedAt = useUiStore((s) => s.setLastUpdatedAt);

  const load = useCallback(async (page = meta.page, options = { silent: false }) => {
    if (options.silent) setIsRefreshing(true);
    else setLoading(true);

    try {
      const res = await getDocuments({
        page,
        pageSize: PAGE_SIZES.documents,
        search: debouncedSearch,
        status,
        sortBy,
        sortDir,
      });
      setRows(res.items);
      setMeta({ page: res.page, pages: res.pages, total: res.total });
      setLastUpdatedAt(new Date().toISOString());
    } finally {
      if (options.silent) setIsRefreshing(false);
      else setLoading(false);
    }
  }, [debouncedSearch, status, sortBy, sortDir, meta.page, setLastUpdatedAt]);

  useEffect(() => {
    load(1, { silent: false });
  }, [debouncedSearch, status, sortBy, sortDir, refreshTick, load]);

  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortDir((v) => (v === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(field);
      setSortDir('asc');
    }
  };

  const onUpload = async (files) => {
    const result = await uploadDocuments(files);
    await load(1, { silent: false });
    return result;
  };

  const onDelete = async () => {
    if (!deleteTarget) return;
    await deleteDocument(deleteTarget.doc_id);
    toast.success('Документ удален');
    setDeleteTarget(null);
    await load(meta.page, { silent: false });
  };

  const onBulkDelete = async () => {
    const result = await bulkDeleteDocuments(selected);
    const deleted = result?.deleted?.length || 0;
    const notFound = result?.not_found?.length || 0;
    const failed = result?.failed?.length || 0;
    toast.success(`Удалено: ${deleted}. Не найдено: ${notFound}. Ошибок: ${failed}`);
    setSelected([]);
    setBulkDeleteOpen(false);
    await load(meta.page, { silent: false });
  };

  const onReindex = async (docId) => {
    await reindexDocument(docId);
    toast.success('Переиндексация запущена');
    await load(meta.page, { silent: true });
  };

  return (
    <div className="space-y-4">
      <Card
        title="Документы"
        right={(
          <div className="flex items-center gap-2">
            {isRefreshing && <span className="text-xs text-muted">Обновление...</span>}
            <Button onClick={() => setUploadOpen(true)}>+ Загрузить файл</Button>
          </div>
        )}
      >
        <div className="mb-3 flex flex-wrap gap-2">
          <input className="rounded-md border border-slate-300 px-3 py-2 text-sm" placeholder="Поиск по имени..." value={search} onChange={(e) => setSearch(e.target.value)} />
          <select className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="all">All</option>
            <option value="completed">completed</option>
            <option value="processing">processing</option>
            <option value="error">error</option>
          </select>
          <Button variant="secondary" onClick={() => { setSearch(''); setStatus('all'); setSortBy('uploaded_at'); setSortDir('desc'); }}>Сброс</Button>
          {selected.length > 0 && <Button variant="danger" onClick={() => setBulkDeleteOpen(true)}>Удалить выбранные ({selected.length})</Button>}
        </div>

        {loading ? (
          <TableSkeleton rows={8} cols={7} />
        ) : rows.length === 0 ? (
          <EmptyState title="Документов нет" description="Попробуйте изменить фильтры." />
        ) : (
          <div className="overflow-auto">
            <table className="table-sticky min-w-full text-sm">
              <thead>
                <tr className="bg-slate-100 text-left">
                  <th className="p-2"><input type="checkbox" onChange={(e) => setSelected(e.target.checked ? rows.map((r) => r.doc_id) : [])} /></th>
                  <th className="cursor-pointer p-2" onClick={() => toggleSort('filename')}>Имя файла</th>
                  <th className="cursor-pointer p-2" onClick={() => toggleSort('status')}>Статус</th>
                  <th className="p-2">Чанки</th>
                  <th className="cursor-pointer p-2" onClick={() => toggleSort('uploaded_at')}>Загружен</th>
                  <th className="p-2">Размер</th>
                  <th className="p-2">Действия</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.doc_id} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="p-2">
                      <input
                        type="checkbox"
                        checked={selected.includes(row.doc_id)}
                        onChange={(e) => {
                          setSelected((prev) => (e.target.checked ? [...prev, row.doc_id] : prev.filter((x) => x !== row.doc_id)));
                        }}
                      />
                    </td>
                    <td className="p-2">{row.filename}</td>
                    <td className="p-2"><Badge value={row.status} /></td>
                    <td className="p-2">{row.chunk_count ?? '--'}</td>
                    <td className="p-2">{formatDateTime(row.uploaded_at)}</td>
                    <td className="p-2">{row.size_mb} MB</td>
                    <td className="p-2">
                      <div className="flex gap-2">
                        <Link className="text-accent hover:underline" to={`/documents/${row.doc_id}`}>Детали</Link>
                        {row.status === 'error' && <button className="text-warning hover:underline" onClick={() => onReindex(row.doc_id)}>Повторить</button>}
                        <button className="text-danger hover:underline" onClick={() => setDeleteTarget(row)}>Удалить</button>
                      </div>
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
      </Card>

      <UploadModal open={uploadOpen} onClose={() => setUploadOpen(false)} onUpload={onUpload} />
      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={onDelete}
        title="Удалить документ"
        description={`Подтвердите удаление: ${deleteTarget?.filename || ''}`}
        danger
        confirmText="Удалить"
      />
      <ConfirmDialog
        open={bulkDeleteOpen}
        onClose={() => setBulkDeleteOpen(false)}
        onConfirm={onBulkDelete}
        title="Удалить выбранные"
        description="Действие необратимо"
        danger
        confirmText="Удалить все"
      />
    </div>
  );
}
