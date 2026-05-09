import Redis from 'ioredis';

export let redisClient: Redis;
export let redisSubscriber: Redis;

export async function setupRedis(): Promise<void> {
  const url = process.env.REDIS_URL || 'redis://localhost:6379';

  try {
    redisClient = new Redis(url, {
      maxRetriesPerRequest: 1,
      connectTimeout: 10000,
    });

    redisSubscriber = new Redis(url, { 
      connectTimeout: 10000,
    });

    redisClient.on('connect', () => console.log('✅ Redis connected successfully'));
    redisClient.on('ready', () => console.log('✅ Redis is ready'));
    redisClient.on('error', (err) => {
      console.warn('⚠️ Redis Connection Error:', err.message);
    });

    // Force connection test
    await redisClient.ping();
  } catch (err) {
    console.error('❌ Redis setup failed to connect:', err);
  }
}

// ─── Job Queue Helpers ────────────────────────────────────────────────────────
export async function enqueueInvestigation(payload: {
  investigationId: string;
  url: string;
  type: string;
  userId: string;
}): Promise<void> {
  await redisClient.lpush('investigation:queue', JSON.stringify(payload));
  await redisClient.publish('investigation:queued', JSON.stringify(payload));
}

// ─── Pub/Sub Helpers ──────────────────────────────────────────────────────────
export async function publishAgentEvent(
  investigationId: string,
  event: object
): Promise<void> {
  const channel = `investigation:${investigationId}:events`;
  await redisClient.publish(channel, JSON.stringify(event));
}

// ─── Cache Helpers ────────────────────────────────────────────────────────────
export async function cacheReport(
  investigationId: string,
  report: object,
  ttlSeconds = 3600
): Promise<void> {
  await redisClient.setex(
    `report:${investigationId}`,
    ttlSeconds,
    JSON.stringify(report)
  );
}

export async function getCachedReport(
  investigationId: string
): Promise<object | null> {
  const cached = await redisClient.get(`report:${investigationId}`);
  return cached ? JSON.parse(cached) : null;
}

// ─── Session Store ────────────────────────────────────────────────────────────
export async function setSession(
  sessionId: string,
  data: object,
  ttlSeconds = 86400
): Promise<void> {
  await redisClient.setex(`session:${sessionId}`, ttlSeconds, JSON.stringify(data));
}

export async function getSession(sessionId: string): Promise<object | null> {
  const data = await redisClient.get(`session:${sessionId}`);
  return data ? JSON.parse(data) : null;
}
