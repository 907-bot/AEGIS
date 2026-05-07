import { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { v4 as uuidv4 } from 'uuid';
import { query } from '../db/postgres';

const TriggerSchema = z.object({
  investigationId: z.string().uuid(),
  conditions: z.array(z.object({
    type: z.enum(['confidence_drop', 'new_entity_detected', 'sentiment_shift',
                  'leadership_change', 'funding_mention', 'regulatory_mention']),
    threshold: z.number().optional(),
    direction: z.enum(['positive', 'negative']).optional(),
    magnitude: z.number().optional(),
    entityTypes: z.array(z.string()).optional(),
    roles: z.array(z.string()).optional(),
    keywords: z.array(z.string()).optional(),
    jurisdictions: z.array(z.string()).optional(),
  })),
  webhookUrl: z.string().url().optional(),
  frequency: z.enum(['realtime', 'hourly', 'daily']).default('daily'),
});

export async function webhookRoutes(fastify: FastifyInstance) {
  fastify.post('/triggers', async (req, reply) => {
    const body = TriggerSchema.safeParse(req.body);
    if (!body.success) return reply.status(400).send({ error: body.error.flatten() });

    const userId = (req.headers['x-user-id'] as string) || 'demo-user';
    const { investigationId, conditions, webhookUrl, frequency } = body.data;
    const id = uuidv4();

    await query(
      `INSERT INTO trigger_configs(id, investigation_id, user_id, conditions, webhook_url, frequency)
       VALUES($1,$2,$3,$4,$5,$6)`,
      [id, investigationId, userId, JSON.stringify(conditions), webhookUrl, frequency]
    );

    return reply.status(201).send({ triggerId: id, message: 'Trigger created' });
  });

  fastify.get('/triggers', async (req, reply) => {
    const userId = (req.headers['x-user-id'] as string) || 'demo-user';
    const triggers = await query(
      `SELECT t.*, i.target_url, i.company_name
       FROM trigger_configs t
       JOIN investigations i ON i.id=t.investigation_id
       WHERE t.user_id=$1 AND t.is_active=true
       ORDER BY t.created_at DESC`,
      [userId]
    );
    return reply.send({ triggers });
  });

  fastify.delete('/triggers/:id', async (req, reply) => {
    const { id } = req.params as { id: string };
    await query(`UPDATE trigger_configs SET is_active=false WHERE id=$1`, [id]);
    return reply.send({ message: 'Trigger deactivated' });
  });
}

