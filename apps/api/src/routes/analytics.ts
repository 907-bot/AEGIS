import { FastifyInstance } from 'fastify';
import { query, queryOne } from '../db/postgres';

export async function analyticsRoutes(fastify: FastifyInstance) {
  // Simulation endpoint
  fastify.post('/simulate', async (req, reply) => {
    const { investigationId, params } = req.body as {
      investigationId: string;
      params: { priceChange: number; regulatoryImpact: number; competitorEntry: boolean; fundingRound: string };
    };

    const report = await queryOne(
      `SELECT r.scenarios, i.vitality_score, i.moat_score, i.risk_score
       FROM reports r JOIN investigations i ON i.id=r.investigation_id
       WHERE r.investigation_id=$1`,
      [investigationId]
    );

    if (!report) return reply.status(404).send({ error: 'Investigation not found' });

    // Monte Carlo simulation (simplified)
    const base = report.vitality_score || 50;
    const simulations = 1000;
    const results = Array.from({ length: simulations }, () => {
      let score = base;
      score += (params.priceChange / 100) * 20 * (Math.random() - 0.3);
      score -= params.regulatoryImpact * 2 * Math.random();
      score -= params.competitorEntry ? 10 * Math.random() : 0;
      const fundingBoost = { none: 0, seed: 5, series_a: 10, series_b: 15, ipo: 25 }[params.fundingRound] || 0;
      score += fundingBoost * Math.random();
      return Math.max(0, Math.min(100, score));
    });

    results.sort((a, b) => a - b);
    const p10 = results[Math.floor(simulations * 0.1)];
    const p50 = results[Math.floor(simulations * 0.5)];
    const p90 = results[Math.floor(simulations * 0.9)];

    return reply.send({
      scenarios: {
        bear: { score: Math.round(p10), label: 'Bear Case (10th percentile)' },
        base: { score: Math.round(p50), label: 'Base Case (50th percentile)' },
        bull: { score: Math.round(p90), label: 'Bull Case (90th percentile)' },
      },
      distribution: results.filter((_, i) => i % 50 === 0),
      params,
    });
  });

  fastify.get('/dashboard', async (req, reply) => {
    const userId = (req.headers['x-user-id'] as string) || 'demo-user';
    const [stats] = await query(`
      SELECT
        COUNT(*)                                        AS total_investigations,
        COUNT(*) FILTER (WHERE status='completed')      AS completed,
        COUNT(*) FILTER (WHERE status='running')        AS running,
        AVG(confidence_score)::DECIMAL(3,2)             AS avg_confidence,
        AVG(vitality_score)::DECIMAL(5,1)               AS avg_vitality,
        AVG(duration_ms)::INTEGER                       AS avg_duration_ms,
        SUM(total_cost_usd)::DECIMAL(10,4)              AS total_cost
      FROM investigations WHERE user_id=$1
    `, [userId]);

    const recent = await query(`
      SELECT id, target_url, company_name, status, vitality_score,
             confidence_score, created_at
      FROM investigations WHERE user_id=$1
      ORDER BY created_at DESC LIMIT 10
    `, [userId]);

    return reply.send({ stats, recent });
  });
}

