import { useState } from 'react';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import Modal from '../../components/ui/Modal';
import Button from '../../components/ui/Button';
import { validateUploadFile } from '../../utils/validators';

export default function UploadModal({ open, onClose, onUpload }) {
  const [files, setFiles] = useState([]);

  const onDrop = (accepted) => {
    if (accepted.length > 10) {
      toast.error('Максимум 10 файлов за загрузку');
      return;
    }
    const prepared = accepted.map((f) => ({ file: f, progress: 0, state: 'ожидание', error: null }));
    setFiles(prepared);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop, multiple: true });

  const handleUpload = async () => {
    const validated = files.map((item) => {
      const err = validateUploadFile(item.file);
      return err ? { ...item, state: 'ошибка', error: err } : item;
    });
    setFiles(validated);
    const valid = validated.filter((x) => !x.error).map((x) => x.file);
    if (!valid.length) return;

    for (let i = 0; i < validated.length; i += 1) {
      if (validated[i].error) continue;
      for (let p = 0; p <= 100; p += 20) {
        setFiles((prev) => prev.map((x, idx) => (idx === i ? { ...x, state: 'загрузка', progress: p } : x)));
        await new Promise((r) => setTimeout(r, 90));
      }
      setFiles((prev) => prev.map((x, idx) => (idx === i ? { ...x, state: 'обработка' } : x)));
    }

    const result = await onUpload(valid);
    const duplicateSet = new Set(result?.duplicates || []);

    setFiles((prev) => prev.map((x) => {
      if (x.error) return x;
      if (duplicateSet.has(x.file.name)) return { ...x, state: 'уже загружен', error: 'Файл с таким именем уже существует' };
      return { ...x, state: 'готов' };
    }));

    if (result?.created?.length) toast.success('Документы загружены');
    if (result?.duplicates?.length) toast.error(`Уже загружен: ${result.duplicates.join(', ')}`);
  };

  return (
    <Modal open={open} onClose={onClose} title="Загрузить документы">
      <div {...getRootProps()} className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center ${isDragActive ? 'border-accent bg-blue-50' : 'border-slate-300'}`}>
        <input {...getInputProps()} />
        <p className="text-sm">Перетащите файлы сюда или нажмите для выбора</p>
        <p className="mt-1 text-xs text-muted">PDF, DOCX, TXT, до 50MB</p>
      </div>
      <div className="mt-4 space-y-2">
        {files.map((item) => (
          <div key={item.file.name} className="rounded border border-slate-200 p-2 text-sm">
            <div className="mb-1 flex justify-between">
              <span>{item.file.name}</span>
              <span className="text-muted">{item.state}</span>
            </div>
            <div className="h-2 rounded bg-slate-200">
              <div className="h-2 rounded bg-accent" style={{ width: `${item.progress}%` }} />
            </div>
            {item.error && <p className="mt-1 text-xs text-danger">{item.error}</p>}
          </div>
        ))}
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>Закрыть</Button>
        <Button onClick={handleUpload}>Загрузить</Button>
      </div>
    </Modal>
  );
}
