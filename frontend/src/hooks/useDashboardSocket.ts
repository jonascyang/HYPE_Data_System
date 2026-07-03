import { useEffect, useMemo, useRef, useState } from 'react';
import type { SocketStatus } from '../types';

type Subscription = {
  panel: string;
  params?: Record<string, string | number | null>;
};

type DashboardUpdate = {
  type: 'dashboard.update' | 'options.update' | 'orderFlow.update';
  snapshotId: number;
  payload: Record<string, unknown>;
};

export function useDashboardSocket(subscriptions: Subscription[], onUpdate: (message: DashboardUpdate) => void) {
  const [status, setStatus] = useState<SocketStatus>('connecting');
  const socketRef = useRef<WebSocket | null>(null);
  const onUpdateRef = useRef(onUpdate);
  const subscriptionsRef = useRef(subscriptions);
  const subscriptionKey = useMemo(() => stableSubscriptionKey(subscriptions), [subscriptions]);
  onUpdateRef.current = onUpdate;
  subscriptionsRef.current = subscriptions;

  useEffect(() => {
    let closed = false;
    let reconnectTimer: number | undefined;
    let staleTimer: number | undefined;

    const connect = () => {
      setStatus(socketRef.current ? 'reconnecting' : 'connecting');
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const socket = new WebSocket(`${protocol}://${window.location.host}/ws/options`);
      socketRef.current = socket;

      socket.onopen = () => {
        setStatus('live');
        socket.send(JSON.stringify({ type: 'subscribe', panels: ['summary', 'atmTerm', 'skewFly'] }));
        sendSubscriptions(socket, subscriptionsRef.current);
        window.clearTimeout(staleTimer);
        staleTimer = window.setTimeout(() => setStatus('stale'), 45000);
      };

      socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (isDashboardUpdate(message)) {
          setStatus('updating');
          onUpdateRef.current(message);
          window.setTimeout(() => setStatus('live'), 240);
          window.clearTimeout(staleTimer);
          staleTimer = window.setTimeout(() => setStatus('stale'), 45000);
        }
      };

      socket.onclose = () => {
        window.clearTimeout(staleTimer);
        if (closed) return;
        setStatus('reconnecting');
        reconnectTimer = window.setTimeout(connect, 1500);
      };

      socket.onerror = () => {
        setStatus('offline');
        socket.close();
      };
    };

    connect();
    return () => {
      closed = true;
      window.clearTimeout(reconnectTimer);
      window.clearTimeout(staleTimer);
      socketRef.current?.close();
    };
  }, []);

  useEffect(() => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    sendSubscriptions(socket, subscriptionsRef.current);
  }, [subscriptionKey]);

  return status;
}

function sendSubscriptions(socket: WebSocket, subscriptions: Subscription[]) {
  subscriptions.forEach((subscription) => {
    socket.send(JSON.stringify({ type: 'panel.subscribe', panel: subscription.panel, params: subscription.params ?? {} }));
  });
}

function stableSubscriptionKey(subscriptions: Subscription[]) {
  return subscriptions
    .map((subscription) => {
      const params = subscription.params ?? {};
      const paramKey = Object.keys(params)
        .sort()
        .map((key) => `${key}:${params[key] ?? ''}`)
        .join(',');
      return `${subscription.panel}(${paramKey})`;
    })
    .join('|');
}

function isDashboardUpdate(value: unknown): value is DashboardUpdate {
  if (!value || typeof value !== 'object') return false;
  const type = (value as { type?: unknown }).type;
  return type === 'dashboard.update' || type === 'options.update' || type === 'orderFlow.update';
}
