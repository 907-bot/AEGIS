import { Server, Socket } from 'socket.io';
import type Redis from 'ioredis';

export async function setupSocketIO(io: Server, redis: Redis): Promise<void> {
  const sub = redis.duplicate();
  
  sub.on('connect', () => console.log('📡 Redis Subscriber connected'));
  sub.on('error', (err) => console.error('📡 Redis Subscriber error:', err));

  sub.psubscribe('investigation:*:events', (err) => {
    if (err) console.error('❌ Redis psubscribe error:', err);
    else console.log('✅ Socket.IO subscribed to pattern: investigation:*:events');
  });

  sub.on('pmessage', (pattern, channel, message) => {
    const parts = channel.split(':');
    const investigationId = parts[1];
    try {
      const data = JSON.parse(message);
      // Broadcast to specific room
      io.to(`investigation:${investigationId}`).emit('agent:event', data);
      // Also broadcast to global war-room
      io.to('war-room').emit('agent:event', { investigationId, ...data });
    } catch (err) {
      console.error('❌ Failed to parse Redis message:', err);
    }
  });

  io.on('connection', (socket: Socket) => {
    console.log(`🔌 Client connected: ${socket.id}`);

    // Join investigation room for real-time updates
    socket.on('subscribe:investigation', (investigationId: string) => {
      socket.join(`investigation:${investigationId}`);
      socket.emit('subscribed', { investigationId });
    });

    socket.on('unsubscribe:investigation', (investigationId: string) => {
      socket.leave(`investigation:${investigationId}`);
    });

    // War-room: collaborative intelligence
    socket.on('join:war-room', () => {
      socket.join('war-room');
    });

    // Human feedback injection
    socket.on('inject:hypothesis', async (data: {
      investigationId: string;
      hypothesis: string;
      userId: string;
    }) => {
      // Publish hypothesis to Redis for agents to pick up
      await redis.publish(
        `investigation:${data.investigationId}:hypothesis`,
        JSON.stringify(data)
      );
      io.to(`investigation:${data.investigationId}`).emit('hypothesis:received', data);
    });

    // Annotation: human-AI collaboration
    socket.on('add:annotation', (data: {
      investigationId: string;
      text: string;
      position: string;
      userId: string;
    }) => {
      io.to(`investigation:${data.investigationId}`).emit('annotation:added', {
        ...data,
        timestamp: new Date(),
        socketId: socket.id,
      });
    });

    socket.on('disconnect', () => {
      console.log(`🔌 Client disconnected: ${socket.id}`);
    });
  });
}
