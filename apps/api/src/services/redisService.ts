import Redis from 'ioredis';

export let redisClient: Redis;
export let redisSubscriber: Redis;

export async function setupRedis(): Promise<void> {
  const url = process.env.REDIS_URL || 'redis://localhost:6379';

  redisClient = new Redis(url, {
    maxRetriesPerRequest: 3,
    retryDelayOnFailover: 100,
    lazyConnect: false,
  });

  redisSubscriber = new Redis(url, { lazyConnect: false });

  redisClient.on('connect', () => console.log('✅ Redis connected'));
  redisClient.on('error', (err) => console.error('❌ Redis error:', err));
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
