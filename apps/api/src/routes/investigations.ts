import { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { v4 as uuidv4 } from 'uuid';
import axios from 'axios';
import { query, queryOne, withTransaction } from '../db/postgres';
import { getCachedReport, cacheReport } from '../services/redisService';

const CreateSchema = z.object({
  url: z.string().transform((val) => {
    let clean = val.trim();
    if (!clean.startsWith('http://') && !clean.startsWith('https://')) {
      clean = 'https://' + clean;
    }
    return clean;
  }).pipe(z.string().url()),
  type: z.enum(['competitive', 'due_diligence', 'ipo_readiness', 'market_analysis']).default('competitive'),
  strategyOverrides: z.record(z.string()).optional(),
});

function getOrCreateUserId(headerUserId: string | undefined): string {
  if (!headerUserId) return '00000000-0000-0000-0000-000000000000';
  // If it looks like a UUID, use it; otherwise create a deterministic UUID
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(headerUserId)) {
    return headerUserId;
  }
  // Create deterministic UUID from string using md5-like approach (simplified)
  // For now, just use the default demo user
  return '00000000-0000-0000-0000-000000000000';
}

export async function investigationRoutes(fastify: FastifyInstance) {
  // ── POST /api/v1/investigations ─────────────────────────────────────────
  fastify.post('/', async (request, reply) => {
    try {
      const body = CreateSchema.safeParse(request.body);
      if (!body.success) return reply.status(400).send({ error: body.error.flatten() });

      const { url, type, strategyOverrides } = body.data;
      const strategy_config = strategyOverrides || {};
      const userId = getOrCreateUserId(request.headers['x-user-id'] as string);

      const id = uuidv4();

      await withTransaction(async (client) => {
        // Ensure user exists - upsert on id (primary key)
        await client.query(
          `INSERT INTO users(id, email, name) VALUES($1, $2, 'Demo User')
           ON CONFLICT (id) DO UPDATE SET updated_at = NOW()`,
          [userId, `user-${userId.substring(0, 8)}@aegis.local`]
        );

        await client.query(
          `INSERT INTO investigations(id, user_id, target_url, investigation_type, strategy_config, status)
           VALUES($1,$2,$3,$4,$5,'queued')`,
          [id, userId, url, type, JSON.stringify(strategy_config)]
        );
      });

      // Call Python orchestrator to start the investigation
      let orchestratorUrl = process.env.AGENT_ORCHESTRATOR_URL;
      if (!orchestratorUrl || orchestratorUrl === 'http://localhost:8001' || orchestratorUrl === 'aegis-orchestrator') {
        if (process.env.NODE_ENV === 'production') {
          orchestratorUrl = 'https://aegis-orchestrator.onrender.com';
        } else {
          orchestratorUrl = 'http://localhost:8001';
        }
      }
      if (orchestratorUrl === 'https://aegis-orchestrator' || orchestratorUrl === 'http://aegis-orchestrator') {
        orchestratorUrl = 'https://aegis-orchestrator.onrender.com';
      }
      if (!/^https?:\/\//i.test(orchestratorUrl)) {
        orchestratorUrl = `https://${orchestratorUrl}`;
      }

      axios.post(`${orchestratorUrl}/investigate`, {
        investigation_id: id, url, type, user_id: userId,
      }, { timeout: 45000 }).then(() => {
        fastify.log.info(`Orchestrator ping succeeded at ${orchestratorUrl}`);
      }).catch((err) => {
        fastify.log.error(`Orchestrator ping failed at ${orchestratorUrl}: ${err.message}`);
      });

      return reply.status(201).send({
        investigationId: id,
        status: 'queued',
        wsChannel: `/investigation/${id}/events`,
      });
    } catch (err: any) {
      fastify.log.error(`INVESTIGATION_FAILURE: ${err.message}`);
      return reply.status(500).send({
        error: 'Internal Server Error',
        message: err.message,
        stack: process.env.NODE_ENV === 'development' ? err.stack : undefined
      });
    }
  });

  // ── GET /api/v1/investigations ──────────────────────────────────────────
  fastify.get('/', async (request, reply) => {
    const userId = getOrCreateUserId(request.headers['x-user-id'] as string);
    const rows = await query(
      `SELECT id, target_url, company_name, investigation_type, status,
              confidence_score, vitality_score, moat_score, risk_score,
              created_at, completed_at, duration_ms
       FROM investigations
       WHERE user_id=$1
       ORDER BY created_at DESC
       LIMIT 50`,
      [userId]
    );
    return reply.send({ investigations: rows, total: rows.length });
  });

  // ── GET /api/v1/investigations/:id ──────────────────────────────────────
  fastify.get('/:id', async (request, reply) => {
    const { id } = request.params as { id: string };
    const inv = await queryOne(
      `SELECT i.*, r.executive_summary, r.bull_thesis, r.bear_thesis,
              r.skeptic_analysis, r.final_verdict, r.red_flag_matrix,
              r.moat_analysis, r.scenarios, r.recommendations
       FROM investigations i
       LEFT JOIN reports r ON r.investigation_id = i.id
       WHERE i.id = $1`,
      [id]
    );
    if (!inv) return reply.status(404).send({ error: 'Investigation not found' });
    return reply.send(inv);
  });

  // ── GET /api/v1/investigations/:id/logs ─────────────────────────────────
  fastify.get('/:id/logs', async (request, reply) => {
    const { id } = request.params as { id: string };
    const logs = await query(
      `SELECT agent_type, event_type, current_action, confidence,
              evidence_count, tokens_used, latency_ms, metadata, created_at
       FROM agent_logs
       WHERE investigation_id=$1
       ORDER BY created_at ASC`,
      [id]
    );
    return reply.send({ logs });
  });

  // ── GET /api/v1/investigations/:id/report ───────────────────────────────
  fastify.get('/:id/report', async (request, reply) => {
    const { id } = request.params as { id: string };

    const cached = await getCachedReport(id);
    if (cached) return reply.send(cached);

    const report = await queryOne(
      `SELECT r.*, i.target_url, i.company_name, i.confidence_score,
              i.vitality_score, i.moat_score, i.risk_score
       FROM reports r
       JOIN investigations i ON i.id = r.investigation_id
       WHERE r.investigation_id=$1`,
      [id]
    );
    if (!report) return reply.status(404).send({ error: 'Report not ready yet' });

    await cacheReport(id, report);
    return reply.send(report);
  });

  // ── DELETE /api/v1/investigations/:id ───────────────────────────────────
  fastify.delete('/:id', async (request, reply) => {
    const { id } = request.params as { id: string };
    await query(`UPDATE investigations SET status='cancelled' WHERE id=$1`, [id]);
    return reply.send({ message: 'Investigation cancelled' });
  });

  // ── POST /api/v1/investigations/:id/feedback ────────────────────────────
  fastify.post('/:id/feedback', async (request, reply) => {
    const { id } = request.params as { id: string };
    const { rating, comment } = request.body as { rating: number; comment?: string };

    await query(
      `UPDATE investigations SET metadata = jsonb_set(metadata, '{feedback}',
       $1::jsonb) WHERE id=$2`,
      [JSON.stringify({ rating, comment, submittedAt: new Date() }), id]
    );
    return reply.send({ message: 'Feedback recorded. Thank you!' });
  });

  // ── GET /api/v1/investigations/:id/graph-data ────────────────────────────
  fastify.get('/:id/graph-data', async (request, reply) => {
    const { id } = request.params as { id: string };
    const snapshot = await queryOne(
      `SELECT data FROM knowledge_snapshots
       WHERE investigation_id=$1 AND snapshot_type='knowledge_graph'
       ORDER BY captured_at DESC LIMIT 1`,
      [id]
    );
    return reply.send(snapshot?.data || { nodes: [], edges: [] });
  });
}
