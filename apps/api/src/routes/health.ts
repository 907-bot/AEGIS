import { FastifyInstance } from 'fastify';
import { query } from '../db/postgres';
import { redisClient } from '../services/redisService';

// ─── Health Routes ────────────────────────────────────────────────────────────
export async function healthRoutes(fastify: FastifyInstance) {
  fastify.get('/', async (_req, reply) => reply.send({ status: 'ok', service: 'api' }));
  
  fastify.get('/live', async (_req, reply) => reply.send({ status: 'ok' }));

  fastify.get('/ready', async (_req, reply) => {
    try {
      await redisClient.ping();
      await query('SELECT 1');
      return reply.send({ status: 'ready', services: { redis: 'ok', postgres: 'ok' } });
    } catch (err: any) {
      return reply.status(503).send({ status: 'degraded', error: err.message });
    }
  });

  fastify.get('/metrics', async (_req, reply) => {
    const [counts] = await query(`
      SELECT
        COUNT(*) FILTER (WHERE status='queued')    AS queued,
        COUNT(*) FILTER (WHERE status='running')   AS running,
        COUNT(*) FILTER (WHERE status='completed') AS completed,
        COUNT(*) FILTER (WHERE status='failed')    AS failed
      FROM investigations
      WHERE created_at > NOW() - INTERVAL '24 hours'
    `);
    return reply.send({ uptime: process.uptime(), investigations24h: counts });
  });
}
