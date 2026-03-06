import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import Card from '../../components/ui/Card';
import Badge from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import TableSkeleton from '../../components/ui/TableSkeleton';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import { blockUser, getUserById } from '../../api/adminApi';
import { formatDateTime, initialsFromName } from '../../utils/formatters';

export default function UserDetail() {
  const { userId } = useParams();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setUser(await getUserById(userId));
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <TableSkeleton rows={6} cols={2} />;
  if (!user) return <div>Пользователь не найден</div>;

  const onToggleBlock = async () => {
    await blockUser(user.user_id, !user.is_blocked);
    toast.success(user.is_blocked ? 'Пользователь разблокирован' : 'Пользователь заблокирован');
    setConfirmOpen(false);
    await load();
  };

  return (
    <div className="space-y-4">
      <Link to="/users" className="text-sm text-accent hover:underline">Назад</Link>
      <Card>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent/10 font-semibold text-accent">
              {initialsFromName(user.username)}
            </div>
            <div>
              <h2 className="text-2xl font-semibold">{user.username}</h2>
              <p className="text-sm text-muted">Зарегистрирован: {formatDateTime(user.registered_at)}</p>
              <p className="mono text-xs text-muted">user_id: {user.user_id}</p>
            </div>
          </div>
          <Badge value={user.is_blocked ? 'blocked' : 'active'} />
        </div>
      </Card>

      <Card title="Статистика">
        <div className="grid grid-cols-3 gap-2 text-sm">
          <div className="rounded border border-slate-200 p-3">Чатов: <span className="font-semibold">{user.chats_count}</span></div>
          <div className="rounded border border-slate-200 p-3">Сообщений: <span className="font-semibold">{user.messages_count}</span></div>
          <div className="rounded border border-slate-200 p-3">Документов: <span className="font-semibold">{user.documents_count}</span></div>
        </div>
      </Card>

      <Card title="Последние чаты">
        <div className="space-y-2">
          {user.recent_chats.map((chat) => (
            <div key={chat.chat_id} className="rounded border border-slate-200 p-3 text-sm">
              <p className="font-medium">{chat.title}</p>
              <p className="text-muted">{formatDateTime(chat.last_message_at)} | {chat.messages_count} сообщ.</p>
            </div>
          ))}
        </div>
      </Card>

      {user.username !== 'admin' && (
        <Button variant={user.is_blocked ? 'primary' : 'danger'} onClick={() => setConfirmOpen(true)}>
          {user.is_blocked ? 'Разблокировать пользователя' : 'Заблокировать пользователя'}
        </Button>
      )}

      <ConfirmDialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={onToggleBlock}
        title={user.is_blocked ? 'Разблокировать пользователя' : 'Заблокировать пользователя'}
        description="Действие будет применено сразу."
        danger={!user.is_blocked}
        confirmText="Подтвердить"
      />
    </div>
  );
}
