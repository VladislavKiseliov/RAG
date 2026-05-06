import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import Badge from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import TableSkeleton from '../../components/ui/TableSkeleton';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import { deleteDocument, getDocumentById, getDownloadUrl, reindexDocument } from '../../api/adminApi';
import { formatDateTime } from '../../utils/formatters';

export default function DocumentDetail() {
  const { docId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [doc, setDoc] = useState(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmName, setConfirmName] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getDocumentById(docId);
      setDoc(data);
    } finally {
      setLoading(false);
    }
  }, [docId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <TableSkeleton rows={5} cols={2} />;
  if (!doc) return <div>Документ не найден</div>;

  const copyValue = async (v) => {
    await navigator.clipboard.writeText(v || '');
    toast.success('Скопировано');
  };

  const onDelete = async () => {
    if (confirmName !== doc.filename) return toast.error('Имя файла не совпадает');
    await deleteDocument(doc.doc_id);
    toast.success('Документ удален');
    navigate('/documents');
  };

  return (
    <div className="space-y-4">
      <Link to="/documents" className="text-sm text-accent hover:underline">Назад к списку</Link>
      <Card>
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-semibold">{doc.filename}</h2>
          <Badge value={doc.status} />
        </div>
      </Card>

      <Card title="Основная информация">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <p>Размер: <span className="font-medium">{doc.size_mb} MB</span></p>
          <p>Загружен: <span className="font-medium">{formatDateTime(doc.uploaded_at)}</span></p>
          <p className="mono">doc_id: {doc.doc_id}</p>
          <Button variant="secondary" className="w-fit" onClick={() => copyValue(doc.doc_id)}>Копировать</Button>
          <p className="mono">s3key: {doc.s3key}</p>
          <Button variant="secondary" className="w-fit" onClick={() => copyValue(doc.s3key)}>Копировать</Button>
          <p className="mono">hash: {doc.file_hash}</p>
          <Button variant="secondary" className="w-fit" onClick={() => copyValue(doc.file_hash)}>Копировать</Button>
        </div>
      </Card>

      <Card title="Индексация">
        <div className="grid grid-cols-2 gap-2 text-sm">
          <p>Чанков: <span className="font-semibold">{doc.chunk_count ?? '--'}</span></p>
          <p>Модель: <span className="font-semibold">{doc.embedding_model}</span></p>
          <p>Коллекция: <span className="mono">{doc.collection}</span></p>
          {doc.error_text && <p className="text-danger">Ошибка: {doc.error_text}</p>}
        </div>
      </Card>

      <div className="flex gap-2">
        <Button
          variant="secondary"
          onClick={async () => {
            const res = await getDownloadUrl(doc.doc_id);
            window.open(res.url, '_blank');
          }}
        >
          Скачать оригинал
        </Button>
        {doc.status === 'error' && (
          <Button
            onClick={async () => {
              await reindexDocument(doc.doc_id);
              toast.success('Переиндексация запущена');
              await load();
            }}
          >
            Повторить индексацию
          </Button>
        )}
        <Button variant="danger" onClick={() => setConfirmOpen(true)}>Удалить документ</Button>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={onDelete}
        title="Подтверждение удаления"
        description="Введите имя файла для подтверждения"
        danger
        confirmText="Удалить"
      >
        <input className="w-full rounded-md border border-slate-300 px-3 py-2" value={confirmName} onChange={(e) => setConfirmName(e.target.value)} />
      </ConfirmDialog>
    </div>
  );
}
