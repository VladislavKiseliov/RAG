import { useCallback, useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import TableSkeleton from '../components/ui/TableSkeleton';
import { getHealth, getQdrantStats } from '../api/adminApi';
import { SERVICE_LABELS } from '../utils/constants';
import { useNotificationsStore } from '../stores/notificationsStore';
import { useUiStore } from '../stores/uiStore';

export default function SystemStatus() {
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState(null);
  const [qdrant, setQdrant] = useState(null);
  const previous = useRef({});
  const addNotification = useNotificationsStore((s) => s.add);
  const refreshTick = useUiStore((s) => s.refreshTick);
  const setLastUpdatedAt = useUiStore((s) => s.setLastUpdatedAt);

  const load = useCallback(async () => {
    setLoading(true);
    const [healthData, qdrantData] = await Promise.all([getHealth(), getQdrantStats()]);
    setHealth(healthData);
    setQdrant(qdrantData);
    setLoading(false);
    setLastUpdatedAt(new Date().toISOString());

    healthData.services.forEach((srv) => {
      if (previous.current[srv.name] && previous.current[srv.name] !== 'offline' && srv.status === 'offline') {
        const text = `Сервис ${srv.name} перешел в offline`;
        toast.error(text);
        addNotification({ level: 'critical', message: text });
      }
      previous.current[srv.name] = srv.status;
    });
  }, [addNotification, setLastUpdatedAt]);

  useEffect(() => {
    load();
  }, [load, refreshTick]);

  if (loading || !health || !qdrant) return <TableSkeleton rows={6} cols={4} />;

  return (
    <div className="space-y-4">
      <section className="grid grid-cols-3 gap-4">
        {health.services.map((srv) => (
          <Card key={srv.name}>
            <p className="text-sm text-muted">{SERVICE_LABELS[srv.name] || srv.name}</p>
            <div className="mt-2 flex items-center justify-between">
              <Badge value={srv.status} />
              <p className="text-sm font-medium">{srv.latency_ms == null ? '-' : `${srv.latency_ms} ms`}</p>
            </div>
          </Card>
        ))}
      </section>
      <Card title="Статистика Qdrant">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <p>Коллекция: <span className="mono">{qdrant.collection}</span></p>
          <p>Векторов: <span className="font-semibold">{qdrant.vectors_count}</span></p>
          <p>Сегментов: <span className="font-semibold">{qdrant.segments_count}</span></p>
          <p>Размер: <span className="font-semibold">{qdrant.disk_data_size_mb} MB</span></p>
          <p>Optimizer: <Badge value={qdrant.optimizer_status === 'ok' ? 'online' : 'degraded'} /></p>
        </div>
      </Card>
    </div>
  );
}
