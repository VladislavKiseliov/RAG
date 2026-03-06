import { useEffect } from 'react';

export function usePolling(callback, intervalMs, enabled = true) {
  useEffect(() => {
    if (!enabled) return undefined;
    callback();
    const timer = setInterval(callback, intervalMs);
    return () => clearInterval(timer);
  }, [callback, intervalMs, enabled]);
}
