import { FastifyInstance } from 'fastify';
import { queryOne } from '../db/postgres';

export async function reportRoutes(fastify: FastifyInstance) {
  fastify.get('/:investigationId/markdown', async (req, reply) => {
    const { investigationId } = req.params as { investigationId: string };
    const report = await queryOne('SELECT raw_markdown FROM reports WHERE investigation_id=$1', [investigationId]);
    if (!report) return reply.status(404).send({ error: 'No report found' });
    reply.header('Content-Type', 'text/markdown');
    return reply.send(report.raw_markdown);
  });

  fastify.get('/:investigationId/pdf', async (req, reply) => {
    const { investigationId } = req.params as { investigationId: string };
    const report = await queryOne('SELECT pdf_url FROM reports WHERE investigation_id=$1', [investigationId]);
    if (!report?.pdf_url) return reply.status(404).send({ error: 'PDF not ready' });
    return reply.redirect(report.pdf_url);
  });
}

