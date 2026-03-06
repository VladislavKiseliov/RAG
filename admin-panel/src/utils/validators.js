const MIME_ALLOW = [
  'application/pdf',
  'text/plain',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
];

const EXT_ALLOW = ['.pdf', '.txt', '.docx'];
const MAX_BYTES = 50 * 1024 * 1024;

export function validateUploadFile(file) {
  if (!file) return 'Файл не выбран';
  const lower = file.name.toLowerCase();
  const extOk = EXT_ALLOW.some((ext) => lower.endsWith(ext));
  if (!MIME_ALLOW.includes(file.type) && !extOk) return 'Недопустимый формат файла';
  if (file.size > MAX_BYTES) return 'Файл превышает 50MB';
  return null;
}
