import { useEffect, useMemo, useRef, useState } from 'react';
import { markPerf, measurePerf, reportPerfSample } from '../perf';
import type { SocketStatus } from '../types';

type Subscription = {
  panel: string;
  params?: Record<string, string | number | null>;
};

type DashboardUpdate = {
  type: 'dashboard.update' | 'options.update' | 'orderFlow.update';
  snapshotId: number;
  payload: Record<string, unknown>;
  revisions?: Record<string, string | number>;
  serverBuildMs?: number;
  payloadBytes?: number;
};

export function useDashboardSocket(subscriptions: Subscription[], onUpdate: (message: DashboardUpdate) => void) {
  const [status, setStatus] = useState<SocketStatus>('connecting');
  const socketRef = useRef<WebSocket | null>(null);
  const onUpdateRef = useRef(onUpdate);
  const subscriptionsRef = useRef(subscriptions);
  const pendingUpdatesRef = useRef<Map<string, DashboardUpdate>>(new Map());
  const flushFrameRef = useRef<number | null>(null);
  const liveTimerRef = useRef<number | null>(null);
  const receiveStartRef = useRef<number | null>(null);
  const revisionsRef = useRef<Record<string, string | number>>({});
  const subscriptionKey = useMemo(() => stableSubscriptionKey(subscriptions), [subscriptions]);
  onUpdateRef.current = onUpdate;
  subscriptionsRef.current = subscriptions;

  useEffect(() => {
    let closed = false;
    let reconnectTimer: number | undefined;
    let staleTimer: number | undefined;

    const markLiveSoon = () => {
      if (liveTimerRef.current != null) window.clearTimeout(liveTimerRef.current);
      liveTimerRef.current = window.setTimeout(() => {
        liveTimerRef.current = null;
        setStatus('live');
      }, 120);
    };

    const scheduleUpdateFlush = () => {
      if (flushFrameRef.current != null) return;
      const flushQueuedAt = markPerf();
      flushFrameRef.current = window.requestAnimationFrame(() => {
        flushFrameRef.current = null;
        measurePerf('ws.message_to_flush', flushQueuedAt, { count: pendingUpdatesRef.current.size });
        const flushStart = markPerf();
        const updates = Array.from(pendingUpdatesRef.current.values());
        pendingUpdatesRef.current.clear();
        for (const update of updates) {
          onUpdateRef.current(update);
        }
        measurePerf('ws.flush', flushStart, { count: updates.length });
        measurePerf('ws.receive_to_merge', receiveStartRef.current, { count: updates.length });
        receiveStartRef.current = null;
        markLiveSoon();
      });
    };

    const connect = () => {
      setStatus(socketRef.current ? 'reconnecting' : 'connecting');
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const socket = new WebSocket(`${protocol}://${window.location.host}/ws/options`);
      socketRef.current = socket;

      socket.onopen = () => {
        setStatus('live');
        revisionsRef.current = {};
        socket.send(JSON.stringify({ type: 'subscribe', panels: ['summary', 'atmTerm', 'skewFly'] }));
        sendSubscriptions(socket, subscriptionsRef.current);
        window.clearTimeout(staleTimer);
        staleTimer = window.setTimeout(() => setStatus('stale'), 45000);
      };

      socket.onmessage = (event) => {
        const parseStart = markPerf();
        receiveStartRef.current = parseStart;
        const message = JSON.parse(event.data);
        measurePerf('ws.parse', parseStart, websocketMessagePerfDetail(message));
        if (isDashboardUpdate(message)) {
          reportWebsocketServerPerf(message);
          const nextMessage = filterFreshPayload(message, revisionsRef.current);
          if (!nextMessage) return;
          setStatus('updating');
          pendingUpdatesRef.current.set(updateKey(nextMessage), nextMessage);
          scheduleUpdateFlush();
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
      if (liveTimerRef.current != null) window.clearTimeout(liveTimerRef.current);
      if (flushFrameRef.current != null) window.cancelAnimationFrame(flushFrameRef.current);
      pendingUpdatesRef.current.clear();
      socketRef.current?.close();
    };
  }, []);

  useEffect(() => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    resetSubscribedRevisions(revisionsRef.current, subscriptionsRef.current);
    sendSubscriptions(socket, subscriptionsRef.current);
  }, [subscriptionKey]);

  return status;
}

function websocketMessagePerfDetail(message: unknown) {
  if (!message || typeof message !== 'object') return undefined;
  const payload = (message as { payload?: unknown }).payload;
  return {
    type: String((message as { type?: unknown }).type ?? 'unknown'),
    panels: payload && typeof payload === 'object' ? Object.keys(payload).join(',') : '',
    payloadBytes: (message as { payloadBytes?: unknown }).payloadBytes ?? null,
    serverBuildMs: (message as { serverBuildMs?: unknown }).serverBuildMs ?? null,
  };
}

function reportWebsocketServerPerf(message: DashboardUpdate) {
  if (typeof message.serverBuildMs === 'number') {
    reportPerfSample('ws.server_build', message.serverBuildMs, {
      type: message.type,
      panels: Object.keys(message.payload).join(','),
    });
  }
  if (typeof message.payloadBytes === 'number') {
    reportPerfSample('ws.payload_bytes', message.payloadBytes, {
      type: message.type,
      panels: Object.keys(message.payload).join(','),
    });
  }
}

function sendSubscriptions(socket: WebSocket, subscriptions: Subscription[]) {
  subscriptions.forEach((subscription) => {
    socket.send(JSON.stringify({ type: 'panel.subscribe', panel: subscription.panel, params: subscription.params ?? {} }));
  });
}

function resetSubscribedRevisions(
  revisions: Record<string, string | number>,
  subscriptions: Subscription[],
) {
  subscriptions.forEach((subscription) => {
    delete revisions[subscription.panel];
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

function updateKey(message: DashboardUpdate) {
  const panels = Object.keys(message.payload).sort().join(',');
  return `${message.type}:${panels || 'empty'}`;
}

function filterFreshPayload(
  message: DashboardUpdate,
  revisions: Record<string, string | number>,
): DashboardUpdate | null {
  if (!message.revisions || Object.keys(message.revisions).length === 0) return message;
  const payload: Record<string, unknown> = {};
  const nextRevisions: Record<string, string | number> = {};

  for (const [panel, value] of Object.entries(message.payload)) {
    const revision = message.revisions[panel];
    if (revision == null) {
      payload[panel] = value;
      continue;
    }
    if (revisions[panel] === revision) continue;
    revisions[panel] = revision;
    payload[panel] = value;
    nextRevisions[panel] = revision;
  }

  return Object.keys(payload).length === 0
    ? null
    : { ...message, payload, revisions: nextRevisions };
}

function isDashboardUpdate(value: unknown): value is DashboardUpdate {
  if (!value || typeof value !== 'object') return false;
  const type = (value as { type?: unknown }).type;
  return type === 'dashboard.update' || type === 'options.update' || type === 'orderFlow.update';
}
