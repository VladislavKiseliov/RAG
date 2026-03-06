import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';

dayjs.extend(relativeTime);

export function formatDateTime(value) {
  if (!value) return '-';
  return dayjs(value).format('DD.MM.YYYY HH:mm');
}

export function formatRelative(value) {
  if (!value) return '-';
  return dayjs(value).fromNow();
}

export function shortId(value, max = 8) {
  if (!value) return '-';
  return `${value.slice(0, max)}...`;
}

export function initialsFromName(name) {
  if (!name) return '??';
  const parts = name.split(/[.\s_-]+/).filter(Boolean);
  return (parts[0]?.[0] || '?').toUpperCase() + (parts[1]?.[0] || parts[0]?.[1] || '?').toUpperCase();
}
