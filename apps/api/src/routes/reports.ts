import { FastifyInstance } from 'fastify';
import { queryOne } from '../db/postgres';
import PDFDocument from 'pdfkit';
import { Readable } from 'stream';

// ─── Colour Palette (matches AEGIS dark theme) ──────────────────────────────
const C = {
  bg:        '#0f1117',
  surface:   '#161b27',
  border:    '#1e293b',
  accent:    '#6366f1',   // indigo-500
  accentLt:  '#818cf8',   // indigo-400
  cyan:      '#22d3ee',
  emerald:   '#34d399',
  amber:     '#fbbf24',
  red:       '#f87171',
  textPrimary:   '#f1f5f9',
  textSecondary: '#94a3b8',
  textMuted:     '#475569',
};

// ─── Markdown → PDF renderer ─────────────────────────────────────────────────
function renderMarkdownToPDF(doc: InstanceType<typeof PDFDocument>, markdown: string) {
  const lines = (markdown || '').split('\n');

  for (const raw of lines) {
    const line = raw.trimEnd();

    if (line.startsWith('# ')) {
      // H1 — section title
      doc.moveDown(0.6)
         .fillColor(C.accentLt)
         .fontSize(18)
         .font('Helvetica-Bold')
         .text(line.slice(2), { continued: false });
      // Underline rule
      const y = doc.y + 4;
      doc.moveTo(doc.page.margins.left, y)
         .lineTo(doc.page.width - doc.page.margins.right, y)
         .strokeColor(C.accent)
         .lineWidth(0.5)
         .stroke();
      doc.moveDown(0.4);

    } else if (line.startsWith('## ')) {
      doc.moveDown(0.5)
         .fillColor(C.accentLt)
         .fontSize(13)
         .font('Helvetica-Bold')
         .text(line.slice(3))
         .moveDown(0.2);

    } else if (line.startsWith('### ')) {
      doc.moveDown(0.3)
         .fillColor(C.cyan)
         .fontSize(11)
         .font('Helvetica-Bold')
         .text(line.slice(4))
         .moveDown(0.1);

    } else if (line.startsWith('- ') || line.startsWith('* ')) {
      // Bullet point
      const content = line.slice(2);
      const x = doc.page.margins.left + 12;
      const bulletY = doc.y + 2;
      doc.circle(doc.page.margins.left + 4, bulletY, 2)
         .fillColor(C.accent)
         .fill();
      doc.fillColor(C.textPrimary)
         .fontSize(9.5)
         .font('Helvetica')
         .text(content, x, bulletY - 2, {
           width: doc.page.width - doc.page.margins.left - doc.page.margins.right - 12,
         })
         .moveDown(0.05);

    } else if (/^\d+\.\s/.test(line)) {
      // Numbered list
      const match = line.match(/^(\d+)\.\s(.*)$/);
      if (match) {
        const num = match[1];
        const content = match[2];
        const x = doc.page.margins.left + 16;
        doc.fillColor(C.accentLt)
           .fontSize(9.5)
           .font('Helvetica-Bold')
           .text(`${num}.`, doc.page.margins.left, doc.y, { continued: true, width: 14 })
           .fillColor(C.textPrimary)
           .font('Helvetica')
           .text(` ${content}`, { width: doc.page.width - doc.page.margins.left - doc.page.margins.right - 16 })
           .moveDown(0.05);
      }

    } else if (line.startsWith('> ')) {
      // Blockquote
      const content = line.slice(2);
      const leftX = doc.page.margins.left;
      const blockY = doc.y;
      doc.rect(leftX, blockY, 3, 14).fill(C.accent);
      doc.fillColor(C.textSecondary)
         .fontSize(9.5)
         .font('Helvetica-Oblique')
         .text(content, leftX + 10, blockY, {
           width: doc.page.width - doc.page.margins.left - doc.page.margins.right - 10,
         })
         .moveDown(0.15);

    } else if (line.startsWith('---') || line.startsWith('===')) {
      // Horizontal rule
      doc.moveDown(0.3);
      const y = doc.y;
      doc.moveTo(doc.page.margins.left, y)
         .lineTo(doc.page.width - doc.page.margins.right, y)
         .strokeColor(C.border)
         .lineWidth(0.5)
         .stroke();
      doc.moveDown(0.3);

    } else if (line === '') {
      doc.moveDown(0.25);

    } else {
      // Regular paragraph — handle **bold** inline
      doc.fillColor(C.textPrimary)
         .fontSize(9.5)
         .font('Helvetica')
         .text(line.replace(/\*\*(.*?)\*\*/g, '$1'), {
           // pdfkit doesn't support inline bold easily; strip markers for now
           lineGap: 2,
         })
         .moveDown(0.05);
    }
  }
}

// ─── Draw the cover page ─────────────────────────────────────────────────────
function drawCoverPage(
  doc: InstanceType<typeof PDFDocument>,
  companyName: string,
  targetUrl: string,
  verdict: string,
  scores: { vitality: number; moat: number; risk: number; confidence: number },
) {
  const W = doc.page.width;
  const H = doc.page.height;

  // Background
  doc.rect(0, 0, W, H).fill(C.bg);

  // Top accent bar
  doc.rect(0, 0, W, 4).fill(C.accent);

  // AEGIS logo text
  doc.fillColor(C.accentLt)
     .fontSize(11)
     .font('Helvetica-Bold')
     .text('AEGIS INTELLIGENCE', 50, 28, { align: 'left' });

  doc.fillColor(C.textMuted)
     .fontSize(8)
     .font('Helvetica')
     .text('Strategic Due Diligence Platform', 50, 44);

  // Date top-right
  const dateStr = new Date().toLocaleDateString('en-GB', { year: 'numeric', month: 'long', day: 'numeric' });
  doc.fillColor(C.textMuted).fontSize(8).text(dateStr, 0, 34, { align: 'right', width: W - 50 });

  // Center hero
  const heroY = H * 0.28;

  // Report type badge
  const badgeText = '  STRATEGIC INTELLIGENCE REPORT  ';
  const badgeW = doc.widthOfString(badgeText) + 20;
  const badgeX = (W - badgeW) / 2;
  doc.roundedRect(badgeX, heroY, badgeW, 20, 10).fill(C.accent + '33');
  doc.fillColor(C.accentLt).fontSize(8).font('Helvetica-Bold').text(badgeText, 0, heroY + 6, { align: 'center', width: W });

  // Company name
  doc.fillColor(C.textPrimary)
     .fontSize(34)
     .font('Helvetica-Bold')
     .text(companyName || 'Company Analysis', 0, heroY + 36, { align: 'center', width: W });

  // Target URL
  doc.fillColor(C.textMuted)
     .fontSize(10)
     .font('Helvetica')
     .text(targetUrl, 0, heroY + 84, { align: 'center', width: W });

  // Divider
  const divY = heroY + 110;
  doc.moveTo(W * 0.3, divY).lineTo(W * 0.7, divY).strokeColor(C.border).lineWidth(0.5).stroke();

  // Verdict badge
  const verdictColor = verdict === 'strong_buy' || verdict === 'buy' ? C.emerald :
                       verdict === 'hold' || verdict === 'watch' ? C.amber : C.red;
  const verdictLabel = verdict.toUpperCase().replace(/_/g, ' ');
  doc.roundedRect(W / 2 - 60, divY + 18, 120, 28, 6).fill(verdictColor + '22');
  doc.fillColor(verdictColor).fontSize(13).font('Helvetica-Bold')
     .text(verdictLabel, 0, divY + 26, { align: 'center', width: W });

  // Score grid
  const scoreY = divY + 70;
  const scoreItems = [
    { label: 'Vitality', value: scores.vitality, color: C.cyan },
    { label: 'Moat',     value: scores.moat,     color: C.accent },
    { label: 'Risk',     value: scores.risk,      color: C.red },
    { label: 'Confidence', value: Math.round(scores.confidence * 100), color: C.emerald },
  ];
  const colW = (W - 100) / 4;
  scoreItems.forEach((s, i) => {
    const cx = 50 + colW * i + colW / 2;
    // Circle bg
    doc.circle(cx, scoreY + 30, 30).fill(C.surface);
    doc.circle(cx, scoreY + 30, 30).stroke(s.color + '55');
    // Score number
    doc.fillColor(s.color).fontSize(18).font('Helvetica-Bold')
       .text(`${s.value}`, cx - 20, scoreY + 20, { width: 40, align: 'center' });
    // Label
    doc.fillColor(C.textSecondary).fontSize(8).font('Helvetica')
       .text(s.label, cx - 30, scoreY + 68, { width: 60, align: 'center' });
  });

  // Footer
  doc.fillColor(C.textMuted).fontSize(7).font('Helvetica')
     .text(
       'This report was generated by AEGIS multi-agent intelligence system. For informational purposes only.',
       50, H - 40, { width: W - 100, align: 'center' }
     );
  doc.rect(0, H - 4, W, 4).fill(C.accent);
}

// ─── Build the full PDF ───────────────────────────────────────────────────────
function buildPDF(report: Record<string, any>): Buffer {
  const chunks: Buffer[] = [];
  const doc = new PDFDocument({
    size: 'A4',
    margins: { top: 50, bottom: 50, left: 50, right: 50 },
    info: {
      Title: `AEGIS Report — ${report.company_name || report.target_url}`,
      Author: 'AEGIS Intelligence Platform',
      Subject: 'Strategic Due Diligence',
    },
    autoFirstPage: false,
  });

  doc.on('data', (chunk: Buffer) => chunks.push(chunk));

  // ── Cover Page ─────────────────────────────────────────────────────────────
  doc.addPage({ size: 'A4' });
  drawCoverPage(
    doc,
    report.company_name || report.target_url || 'Unknown',
    report.target_url || '',
    report.final_verdict || 'hold',
    {
      vitality:   report.vitality_score  ?? 0,
      moat:       report.moat_score      ?? 0,
      risk:       report.risk_score      ?? 0,
      confidence: report.confidence_score ?? 0.75,
    }
  );

  // ── Content pages ──────────────────────────────────────────────────────────
  doc.addPage({ size: 'A4' });

  // Page background
  const W = doc.page.width;
  const H = doc.page.height;
  doc.rect(0, 0, W, H).fill(C.bg);

  // Running header
  const drawPageHeader = () => {
    doc.rect(0, 0, W, 36).fill(C.surface);
    doc.fillColor(C.accentLt).fontSize(8).font('Helvetica-Bold')
       .text('AEGIS INTELLIGENCE', 50, 13);
    doc.fillColor(C.textMuted).fontSize(8)
       .text(report.company_name || report.target_url || '', 0, 13, { align: 'right', width: W - 50 });
    doc.moveTo(0, 36).lineTo(W, 36).strokeColor(C.accent).lineWidth(0.5).stroke();
  };
  drawPageHeader();

  // Page event to auto-add headers and dark backgrounds on new pages
  doc.on('pageAdded', () => {
    doc.rect(0, 0, doc.page.width, doc.page.height).fill(C.bg);
    drawPageHeader();
    doc.y = 50;
  });

  doc.y = 50;

  // Render the full raw_markdown
  if (report.raw_markdown) {
    renderMarkdownToPDF(doc, report.raw_markdown);
  } else {
    // Fallback: build from structured fields
    const sections = [
      { title: '# Executive Summary', content: report.executive_summary },
      { title: '# Bull Thesis',       content: report.bull_thesis },
      { title: '# Bear Thesis',       content: report.bear_thesis },
      { title: '# Skeptic Analysis',  content: report.skeptic_analysis },
      { title: '# Final Verdict',     content: report.final_verdict },
    ];
    for (const s of sections) {
      if (s.content) {
        renderMarkdownToPDF(doc, `${s.title}\n\n${s.content}\n\n`);
      }
    }
  }

  doc.end();

  return Buffer.concat(chunks);
}

// ─── Route Definitions ────────────────────────────────────────────────────────
export async function reportRoutes(fastify: FastifyInstance) {

  // GET /reports/:investigationId/markdown — download raw markdown file
  fastify.get('/:investigationId/markdown', async (req, reply) => {
    const { investigationId } = req.params as { investigationId: string };
    const report = await queryOne(
      'SELECT raw_markdown, company_name, target_url FROM reports r JOIN investigations i ON r.investigation_id = i.id WHERE r.investigation_id=$1',
      [investigationId]
    );
    if (!report) return reply.status(404).send({ error: 'No report found' });

    const filename = `aegis-report-${(report.company_name || investigationId).toLowerCase().replace(/\s+/g, '-')}.md`;
    reply.header('Content-Type', 'text/markdown; charset=utf-8');
    reply.header('Content-Disposition', `attachment; filename="${filename}"`);
    return reply.send(report.raw_markdown);
  });

  // GET /reports/:investigationId/pdf — generate and stream PDF on-the-fly
  fastify.get('/:investigationId/pdf', async (req, reply) => {
    const { investigationId } = req.params as { investigationId: string };

    const report = await queryOne(
      `SELECT r.*, i.target_url, i.company_name, i.final_verdict,
              i.vitality_score, i.moat_score, i.risk_score, i.confidence_score
       FROM reports r
       JOIN investigations i ON r.investigation_id = i.id
       WHERE r.investigation_id = $1`,
      [investigationId]
    );

    if (!report) return reply.status(404).send({ error: 'No report found' });

    let pdfBuffer: Buffer;
    try {
      pdfBuffer = buildPDF(report);
    } catch (err: any) {
      fastify.log.error(`PDF generation failed for ${investigationId}: ${err.message}`);
      return reply.status(500).send({ error: 'PDF generation failed', detail: err.message });
    }

    const filename = `aegis-report-${(report.company_name || investigationId).toLowerCase().replace(/\s+/g, '-')}.pdf`;
    reply.header('Content-Type', 'application/pdf');
    reply.header('Content-Disposition', `attachment; filename="${filename}"`);
    reply.header('Content-Length', pdfBuffer.length);
    return reply.send(pdfBuffer);
  });
}
