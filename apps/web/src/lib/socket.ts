import { io, Socket } from 'socket.io-client';

let socket: Socket | null = null;

export function createSocket(): Socket {
  if (socket?.connected) return socket;

  const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'http://localhost:3000';

  socket = io(WS_URL, {
    transports: ['websocket', 'polling'],
    reconnectionAttempts: 10,
    reconnectionDelay: 1000,
    timeout: 10000,
  });

  socket.on('connect', () => console.log('[AEGIS Socket] Connected:', socket?.id));
  socket.on('disconnect', r => console.log('[AEGIS Socket] Disconnected:', r));
  socket.on('connect_error', e => console.warn('[AEGIS Socket] Error:', e.message));

  return socket;
}

export function getSocket(): Socket | null {
  return socket;
}
