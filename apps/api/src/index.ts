import * as dotenv from 'dotenv';
import path from 'path';

// Load environment variables from root .env
dotenv.config({ path: path.resolve(__dirname, '../../../.env') });

import Fastify from 'fastify';
import cors from '@fastify/cors';
import helmet from '@fastify/helmet';
import rateLimit from '@fastify/rate-limit';
import swagger from '@fastify/swagger';
import swaggerUi from '@fastify/swagger-ui';
import { Server } from 'socket.io';
import { createServer } from 'http';

import { investigationRoutes } from './routes/investigations';
import { reportRoutes } from './routes/reports';
import { healthRoutes } from './routes/health';
import { analyticsRoutes } from './routes/analytics';
import { webhookRoutes } from './routes/webhooks';
import { setupRedis, redisClient } from './services/redisService';
import { setupDatabase } from './db/postgres';
import { setupSocketIO } from './plugins/socketio';

const PORT = parseInt(process.env.PORT || '3000', 10);
const HOST = '0.0.0.0';

async function buildApp() {
  const fastify = Fastify({
    logger: {
      level: process.env.NODE_ENV === 'production' ? 'info' : 'debug',
      transport: process.env.NODE_ENV !== 'production'
        ? { target: 'pino-pretty', options: { colorize: true } }
        : undefined,
    },
  });

  // ─── Security ──────────────────────────────────────────────────────────
  await fastify.register(helmet, {
    contentSecurityPolicy: false, // Managed by Cloudflare in prod
  });

  await fastify.register(cors, {
    origin: process.env.CORS_ORIGIN || '*',
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'X-User-ID'],
  });

  await fastify.register(rateLimit, {
    max: 300,
    timeWindow: '1 minute',
    errorResponseBuilder: () => ({
      code: 429,
      error: 'Too Many Requests',
      message: 'Rate limit exceeded. Please slow down.',
    }),
  });

  // ─── Swagger API Docs ──────────────────────────────────────────────────
  await fastify.register(swagger, {
    openapi: {
      info: {
        title: 'AEGIS API',
        description: 'Autonomous Multi-Agent Strategic Intelligence Platform',
        version: '1.0.0',
      },
      tags: [
        { name: 'investigations', description: 'Investigation endpoints' },
        { name: 'reports', description: 'Report generation endpoints' },
        { name: 'analytics', description: 'Analytics and simulation' },
        { name: 'health', description: 'Health checks' },
      ],
    },
  });

  await fastify.register(swaggerUi, {
    routePrefix: '/docs',
    uiConfig: { docExpansion: 'list', deepLinking: false },
  });

  // ─── Database & Cache ──────────────────────────────────────────────────
  await setupDatabase();
  await setupRedis();

  // ─── Welcome Route ─────────────────────────────────────────────────────
  fastify.get('/', async () => {
    return { 
      service: 'AEGIS API', 
      version: '1.0.0', 
      status: 'online',
      documentation: '/docs' 
    };
  });

  // ─── Routes ───────────────────────────────────────────────────────────
  await fastify.register(healthRoutes, { prefix: '/health' });
  await fastify.register(investigationRoutes, { prefix: '/api/v1/investigations' });
  await fastify.register(reportRoutes, { prefix: '/api/v1/reports' });
  await fastify.register(analyticsRoutes, { prefix: '/api/v1/analytics' });
  await fastify.register(webhookRoutes, { prefix: '/api/v1/webhooks' });

  return fastify;
}

async function main() {
  const fastify = await buildApp();

  // ─── Socket.IO (Real-time) ─────────────────────────────────────────────
  const io = new Server(fastify.server, {
    cors: { origin: '*', methods: ['GET', 'POST'] },
  });

  await setupSocketIO(io, redisClient);

  // ─── Start ─────────────────────────────────────────────────────────────
  try {
    await fastify.listen({ port: PORT, host: HOST });
    fastify.log.info(`🚀 AEGIS API running on http://${HOST}:${PORT}`);
    fastify.log.info(`📚 API Docs available at http://${HOST}:${PORT}/docs`);
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
}

// ─── Graceful Shutdown ─────────────────────────────────────────────────────
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, shutting down...');
  const fastify = await buildApp();
  await fastify.close();
  await redisClient.quit();
  process.exit(0);
});

main();
