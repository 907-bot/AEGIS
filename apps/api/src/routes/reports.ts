import { FastifyInstance } from 'fastify';
import { queryOne } from '../db/postgres';
import PDFDocument from 'pdfkit';
import { Readable } from 'stream';
import nodemailer from 'nodemailer';
import https from 'https';

const C = {
  bg:        '#0f1117',
  surface:   '#161b27',
  border:    '#1e293b',
  accent:    '#6366f1',
  accentLt:  '#818cf8',
  cyan:      '#22d3ee',
  emerald:   '#34d399',
  amber:     '#fbbf24',
  red:       '#f87171',
  pink:      '#f472b6',
  teal:      '#14b8a6',
  textPrimary:   '#f1f5f9',
  textSecondary: '#94a3b8',
  textMuted:     '#475569',
  chartColors: ['#6366f1', '#22d3ee', '#34d399', '#fbbf24', '#f87171', '#f472b6', '#14b8a6', '#a78bfa'],
};

function fetchImageAsBuffer(url: string): Promise<Buffer | null> {
  return new Promise((resolve) => {
    if (!url || !url.startsWith('http')) return resolve(null);
    https.get(url, { timeout: 8000 }, (res) => {
      if (res.statusCode !== 200) { res.resume(); return resolve(null); }
      const chunks: Buffer[] = [];
      res.on('data', (c: Buffer) => chunks.push(c));
      res.on('end', () => resolve(Buffer.concat(chunks)));
    }).on('error', () => resolve(null));
  });
}

function renderMarkdownToPDF(doc: InstanceType<typeof PDFDocument>, markdown: string) {
  const lines = (markdown || '').split('\n');
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (doc.y > doc.page.height - doc.page.margins.bottom - 40) {
      doc.addPage();
    }
    if (line.startsWith('# ')) {
      doc.moveDown(0.6).fillColor(C.accentLt).fontSize(18).font('Helvetica-Bold').text(line.slice(2), { continued: false });
      const y = doc.y + 4;
      doc.moveTo(doc.page.margins.left, y).lineTo(doc.page.width - doc.page.margins.right, y).strokeColor(C.accent).lineWidth(0.5).stroke();
      doc.moveDown(0.4);
    } else if (line.startsWith('## ')) {
      doc.moveDown(0.5).fillColor(C.accentLt).fontSize(13).font('Helvetica-Bold').text(line.slice(3)).moveDown(0.2);
    } else if (line.startsWith('### ')) {
      doc.moveDown(0.3).fillColor(C.cyan).fontSize(11).font('Helvetica-Bold').text(line.slice(4)).moveDown(0.1);
    } else if (line.startsWith('- ') || line.startsWith('* ')) {
      const content = line.slice(2);
      const x = doc.page.margins.left + 12;
      const bulletY = doc.y + 2;
      doc.circle(doc.page.margins.left + 4, bulletY, 2).fillColor(C.accent).fill();
      doc.fillColor(C.textPrimary).fontSize(9.5).font('Helvetica').text(content, x, bulletY - 2, {
        width: doc.page.width - doc.page.margins.left - doc.page.margins.right - 12,
      }).moveDown(0.05);
    } else if (/^\d+\.\s/.test(line)) {
      const match = line.match(/^(\d+)\.\s(.*)$/);
      if (match) {
        const num = match[1], content = match[2];
        const x = doc.page.margins.left + 16;
        doc.fillColor(C.accentLt).fontSize(9.5).font('Helvetica-Bold').text(`${num}.`, doc.page.margins.left, doc.y, { continued: true, width: 14 })
          .fillColor(C.textPrimary).font('Helvetica').text(` ${content}`, { width: doc.page.width - doc.page.margins.left - doc.page.margins.right - 16 }).moveDown(0.05);
      }
    } else if (line.startsWith('> ')) {
      const content = line.slice(2);
      const leftX = doc.page.margins.left, blockY = doc.y;
      doc.rect(leftX, blockY, 3, 14).fill(C.accent);
      doc.fillColor(C.textSecondary).fontSize(9.5).font('Helvetica-Oblique').text(content, leftX + 10, blockY, {
        width: doc.page.width - doc.page.margins.left - doc.page.margins.right - 10,
      }).moveDown(0.15);
    } else if (line.startsWith('---') || line.startsWith('===')) {
      doc.moveDown(0.3);
      const y = doc.y;
      doc.moveTo(doc.page.margins.left, y).lineTo(doc.page.width - doc.page.margins.right, y).strokeColor(C.border).lineWidth(0.5).stroke();
      doc.moveDown(0.3);
    } else if (line === '') {
      doc.moveDown(0.25);
    } else {
      doc.fillColor(C.textPrimary).fontSize(9.5).font('Helvetica').text(line.replace(/\*\*(.*?)\*\*/g, '$1'), { lineGap: 2 }).moveDown(0.05);
    }
  }
}

function drawBarChart(doc: InstanceType<typeof PDFDocument>, data: { label: string; value: number; color?: string }[], x: number, y: number, w: number, h: number, title: string) {
  const maxVal = Math.max(...data.map(d => d.value), 1);
  const barW = Math.min(30, (w - 20) / data.length - 4);
  const chartTop = y + 20;
  const chartH = h - 50;

  doc.fillColor(C.accentLt).fontSize(10).font('Helvetica-Bold').text(title, x, y, { width: w, align: 'center' });

  data.forEach((d, i) => {
    const bx = x + 10 + i * (barW + 6);
    const bh = (d.value / maxVal) * (chartH - 20);
    const by = chartTop + chartH - bh - 20;
    const color = d.color || C.chartColors[i % C.chartColors.length];

    doc.rect(bx, by, barW, bh).fill(color);
    doc.fillColor(C.textPrimary).fontSize(7).font('Helvetica').text(`${d.value}`, bx, by - 10, { width: barW, align: 'center' });
    doc.fillColor(C.textSecondary).fontSize(6.5).font('Helvetica').text(d.label, bx - 4, chartTop + chartH - 14, { width: barW + 8, align: 'center' });
  });

  doc.moveTo(x + 8, chartTop + chartH - 20).lineTo(x + w - 8, chartTop + chartH - 20).strokeColor(C.border).lineWidth(0.5).stroke();
}

function drawPieChart(doc: InstanceType<typeof PDFDocument>, data: { label: string; value: number; color?: string }[], cx: number, cy: number, r: number, title: string) {
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  let startAngle = -Math.PI / 2;
  const d = doc as any;

  d.fillColor(C.accentLt).fontSize(10).font('Helvetica-Bold').text(title, cx - r, cy - r - 20, { width: r * 2, align: 'center' });

  data.forEach((item, i) => {
    const sliceAngle = (item.value / total) * 2 * Math.PI;
    const color = item.color || C.chartColors[i % C.chartColors.length];
    const endAngle = startAngle + sliceAngle;

    d.moveTo(cx, cy);
    d.arc(cx, cy, r, startAngle, endAngle);
    d.closePath();
    d.fillColor(color).fill();

    const midAngle = startAngle + sliceAngle / 2;
    const labelR = r * 0.65;
    const lx = cx + Math.cos(midAngle) * labelR;
    const ly = cy + Math.sin(midAngle) * labelR;
    const pct = ((item.value / total) * 100).toFixed(1);
    if (pct !== '0.0') {
      d.fillColor(C.textPrimary).fontSize(7).font('Helvetica').text(`${pct}%`, lx - 10, ly - 4, { width: 20, align: 'center' });
    }

    startAngle = endAngle;
  });

  const legendY = cy + r + 10;
  data.forEach((item, i) => {
    const color = item.color || C.chartColors[i % C.chartColors.length];
    d.rect(cx - r, legendY + i * 14, 8, 8).fill(color);
    d.fillColor(C.textPrimary).fontSize(7.5).font('Helvetica').text(item.label, cx - r + 12, legendY + i * 14, { width: r * 2 - 20 });
  });
}

function drawScoreGauge(doc: InstanceType<typeof PDFDocument>, label: string, score: number, x: number, y: number, w: number, color: string) {
  doc.roundedRect(x, y, w, 40, 4).fill(C.surface);
  doc.fillColor(C.textSecondary).fontSize(8).font('Helvetica').text(label, x + 10, y + 6);
  const barX = x + 10, barY = y + 22, barW = w - 20, barH = 10;
  doc.roundedRect(barX, barY, barW, barH, 4).fill(C.bg);
  doc.roundedRect(barX, barY, barW * (score / 100), barH, 4).fill(color);
  doc.fillColor(C.textPrimary).fontSize(8).font('Helvetica-Bold').text(`${score}`, barX + barW - 25, barY + 1, { width: 20, align: 'right' });
}

function drawCoverPage(doc: InstanceType<typeof PDFDocument>, companyName: string, targetUrl: string, verdict: string, scores: { vitality: number; moat: number; risk: number; confidence: number }) {
  const W = doc.page.width, H = doc.page.height;
  doc.rect(0, 0, W, H).fill(C.bg);
  doc.rect(0, 0, W, 4).fill(C.accent);

  doc.fillColor(C.accentLt).fontSize(11).font('Helvetica-Bold').text('AEGIS INTELLIGENCE', 50, 28);
  doc.fillColor(C.textMuted).fontSize(8).font('Helvetica').text('Strategic Due Diligence Platform', 50, 44);
  const dateStr = new Date().toLocaleDateString('en-GB', { year: 'numeric', month: 'long', day: 'numeric' });
  doc.fillColor(C.textMuted).fontSize(8).text(dateStr, 0, 34, { align: 'right', width: W - 50 });

  const heroY = H * 0.22;
  const badgeText = '  STRATEGIC INTELLIGENCE REPORT  ';
  const badgeW = doc.widthOfString(badgeText) + 20;
  doc.roundedRect((W - badgeW) / 2, heroY, badgeW, 20, 10).fill(C.accent + '33');
  doc.fillColor(C.accentLt).fontSize(8).font('Helvetica-Bold').text(badgeText, 0, heroY + 6, { align: 'center', width: W });
  doc.fillColor(C.textPrimary).fontSize(34).font('Helvetica-Bold').text(companyName || 'Company Analysis', 0, heroY + 36, { align: 'center', width: W });
  doc.fillColor(C.textMuted).fontSize(10).font('Helvetica').text(targetUrl, 0, heroY + 84, { align: 'center', width: W });

  const divY = heroY + 110;
  doc.moveTo(W * 0.3, divY).lineTo(W * 0.7, divY).strokeColor(C.border).lineWidth(0.5).stroke();

  const verdictColor = verdict === 'strong_buy' || verdict === 'buy' ? C.emerald : verdict === 'hold' || verdict === 'watch' ? C.amber : C.red;
  const verdictLabel = verdict.toUpperCase().replace(/_/g, ' ');
  doc.roundedRect(W / 2 - 60, divY + 18, 120, 28, 6).fill(verdictColor + '22');
  doc.fillColor(verdictColor).fontSize(13).font('Helvetica-Bold').text(verdictLabel, 0, divY + 26, { align: 'center', width: W });

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
    doc.circle(cx, scoreY + 30, 30).fill(C.surface);
    doc.circle(cx, scoreY + 30, 30).stroke(s.color + '55');
    doc.fillColor(s.color).fontSize(18).font('Helvetica-Bold').text(`${s.value}`, cx - 20, scoreY + 20, { width: 40, align: 'center' });
    doc.fillColor(C.textSecondary).fontSize(8).font('Helvetica').text(s.label, cx - 30, scoreY + 68, { width: 60, align: 'center' });
  });

  doc.fillColor(C.textMuted).fontSize(7).font('Helvetica').text('This report was generated by AEGIS multi-agent intelligence system. For informational purposes only.', 50, H - 40, { width: W - 100, align: 'center' });
  doc.rect(0, H - 4, W, 4).fill(C.accent);
}

function drawSectionHeader(doc: InstanceType<typeof PDFDocument>, companyName: string, sectionTitle: string) {
  const W = doc.page.width;
  doc.rect(0, 0, W, 36).fill(C.surface);
  doc.fillColor(C.accentLt).fontSize(8).font('Helvetica-Bold').text('AEGIS INTELLIGENCE', 50, 13);
  doc.fillColor(C.textMuted).fontSize(8).text(companyName || '', 0, 13, { align: 'right', width: W - 50 });
  doc.moveTo(0, 36).lineTo(W, 36).strokeColor(C.accent).lineWidth(0.5).stroke();
  doc.y = 50;

  doc.fillColor(C.accentLt).fontSize(20).font('Helvetica-Bold').text(sectionTitle);
  doc.moveDown(0.3);
  doc.moveTo(doc.page.margins.left, doc.y).lineTo(doc.page.width - doc.page.margins.right, doc.y).strokeColor(C.accent).lineWidth(0.5).stroke();
  doc.moveDown(0.5);
}

function drawFieldRow(doc: InstanceType<typeof PDFDocument>, key: string, value: string, col1X: number, col1W: number, col2X: number, col2W: number) {
  const startY = doc.y;
  doc.fillColor(C.textMuted).fontSize(8.5).font('Helvetica-Bold').text(key, col1X, startY, { width: col1W });
  doc.fillColor(C.textPrimary).fontSize(8.5).font('Helvetica').text(value, col2X, startY, { width: col2W });
  doc.moveDown(0.35);
}

function drawCompanyOverview(doc: InstanceType<typeof PDFDocument>, report: Record<string, any>, logoBuffer?: Buffer | null) {
  drawSectionHeader(doc, report.company_name, 'Company Overview');

  if (logoBuffer && logoBuffer.length > 100) {
    try {
      const maxLogoW = 120, maxLogoH = 60;
      (doc as any).image(logoBuffer, doc.page.width - doc.page.margins.right - maxLogoW, doc.y, { fit: [maxLogoW, maxLogoH], align: 'right', valign: 'top' });
    } catch {}
  }

  const col1X = doc.page.margins.left, col1W = 120, col2X = col1X + col1W, col2W = doc.page.width - doc.page.margins.right - col2X;
  const fmtArr = (v: any) => Array.isArray(v) ? v.join(', ') : (v || 'N/A');
  const fields = [
    ['Company', report.company_name || 'N/A'],
    ['Tagline', report.tagline || 'N/A'],
    ['URL', report.target_url || 'N/A'],
    ['Industry', report.industry || report.industry_category || 'N/A'],
    ['Business Model', report.business_model || 'N/A'],
    ['Pricing Model', report.pricing_model || 'N/A'],
    ['Founded Stage', report.founding_stage || 'N/A'],
    ['Headcount', report.headcount_estimate || report.team_size_estimate || 'N/A'],
    ['CEO', typeof report.ceo === 'object' ? (report.ceo?.name || 'N/A') : (report.ceo || 'N/A')],
    ['Co-Founders', fmtArr(typeof report.co_founders === 'object' && Array.isArray(report.co_founders) ? report.co_founders.map((c: any) => typeof c === 'object' ? c.name : c) : report.co_founders)],
    ['Geographic Presence', fmtArr(report.geographic_presence)],
    ['Office Locations', fmtArr(report.office_locations)],
    ['Branch Offices', fmtArr(report.branch_offices)],
    ['Target Customers', fmtArr(report.target_customers)],
    ['Key Products', fmtArr(report.key_products)],
    ['Funding Stage', report.funding_stage || report.recent_funding_round || 'N/A'],
    ['Total Raised', report.total_raised || 'N/A'],
    ['Valuation', report.valuation ? `$${report.valuation}` : 'N/A'],
    ['Tech Stack', fmtArr(report.tech_stack)],
  ];
  fields.forEach(([k, v]) => drawFieldRow(doc, k, v, col1X, col1W, col2X, col2W));

  doc.moveDown(0.5);
  doc.fillColor(C.accentLt).fontSize(11).font('Helvetica-Bold').text('Description');
  doc.moveDown(0.2);
  doc.fillColor(C.textPrimary).fontSize(9).font('Helvetica').text(report.description || report.executive_summary || 'No description available.', { lineGap: 3 });
}

function drawLeadershipSection(doc: InstanceType<typeof PDFDocument>, report: Record<string, any>) {
  drawSectionHeader(doc, report.company_name, 'Leadership & Team');

  // Use leadership_team from metadata, fall back to leadership field
  let leaders = report.leadership_team || report.leadership || [];
  if (!Array.isArray(leaders)) leaders = [];

  // Also include CEO as first leader if not already in the list
  const ceo = report.ceo;
  if (ceo && typeof ceo === 'object' && ceo.name && !leaders.find((l: any) => l.name === ceo.name)) {
    leaders = [{ name: ceo.name, role: 'CEO', background: ceo.background || '' }, ...leaders];
  }

  if (leaders.length > 0) {
    leaders.slice(0, 8).forEach((l: any, i: number) => {
      if (doc.y > doc.page.height - 100) doc.addPage();
      doc.roundedRect(doc.page.margins.left, doc.y, doc.page.width - doc.page.margins.left - doc.page.margins.right, 50, 4).fill(C.surface);
      doc.circle(doc.page.margins.left + 25, doc.y + 25, 18).fill(C.accent + '33');
      doc.fillColor(C.accentLt).fontSize(14).font('Helvetica-Bold').text(l.name ? l.name.charAt(0).toUpperCase() : '?', doc.page.margins.left + 17, doc.y + 16);
      doc.fillColor(C.textPrimary).fontSize(10).font('Helvetica-Bold').text(l.name || 'Unknown', doc.page.margins.left + 55, doc.y + 8);
      doc.fillColor(C.textSecondary).fontSize(8).font('Helvetica').text(l.role || 'Team Member', doc.page.margins.left + 55, doc.y + 23);
      doc.fillColor(C.textMuted).fontSize(7).font('Helvetica-Oblique').text(l.background || '', doc.page.margins.left + 55, doc.y + 35, { width: doc.page.width - doc.page.margins.left - doc.page.margins.right - 65 });
      doc.moveDown(1.5);
    });
  } else {
    const names = (report.leadership_names || []).map((n: string) => ({ name: n, role: 'Leadership', background: '' }));
    names.slice(0, 8).forEach((l: any) => {
      doc.roundedRect(doc.page.margins.left, doc.y, doc.page.width - doc.page.margins.left - doc.page.margins.right, 40, 4).fill(C.surface);
      doc.circle(doc.page.margins.left + 25, doc.y + 20, 16).fill(C.accent + '33');
      doc.fillColor(C.accentLt).fontSize(12).font('Helvetica-Bold').text(l.name.charAt(0).toUpperCase(), doc.page.margins.left + 18, doc.y + 12);
      doc.fillColor(C.textPrimary).fontSize(10).font('Helvetica-Bold').text(l.name, doc.page.margins.left + 50, doc.y + 8);
      doc.fillColor(C.textSecondary).fontSize(8).font('Helvetica').text(l.role, doc.page.margins.left + 50, doc.y + 23);
      doc.moveDown(1.3);
    });
  }

  const founderBg = report.founder_background || [];
  if (founderBg.length > 0) {
    doc.moveDown(0.5);
    doc.fillColor(C.cyan).fontSize(10).font('Helvetica-Bold').text('Founder Background');
    founderBg.slice(0, 5).forEach((fb: string) => {
      doc.fillColor(C.textPrimary).fontSize(8.5).font('Helvetica').text(`  - ${fb}`);
    });
  }

  doc.moveDown(0.8);
  const gaugeW = (doc.page.width - doc.page.margins.left - doc.page.margins.right) / 2 - 5;
  drawScoreGauge(doc, 'Team Quality Score', report.team_quality_score ?? 70, doc.page.margins.left, doc.y, gaugeW, C.accent);
  drawScoreGauge(doc, 'Hiring Velocity', report.hiring_velocity === 'aggressive' ? 85 : report.hiring_velocity === 'steady' ? 60 : report.hiring_velocity === 'slow' ? 30 : 50, doc.page.margins.left + gaugeW + 10, doc.y - 40, gaugeW, C.cyan);
}

function drawFinancialSection(doc: InstanceType<typeof PDFDocument>, report: Record<string, any>) {
  drawSectionHeader(doc, report.company_name, 'Financial Analysis');

  const col1X = doc.page.margins.left, col1W = 130, col2X = col1X + col1W, col2W = doc.page.width - doc.page.margins.right - col2X;
  const fmtArr = (v: any) => Array.isArray(v) ? v.join(', ') : (v || 'N/A');
  const finFields = [
    ['Revenue Stage', report.revenue_stage || 'N/A'],
    ['Revenue Estimate', report.revenue_estimate_inr || 'N/A'],
    ['Revenue Model', report.revenue_model || 'N/A'],
    ['Pricing Model', report.pricing_model || 'N/A'],
    ['Pricing Transparency', report.pricing_transparency || 'N/A'],
    ['Has Pricing Page', report.has_pricing_page?.toString() || 'N/A'],
    ['Price Points', fmtArr(report.price_points)],
    ['Total Open Roles', report.total_open_roles?.toString() || 'N/A'],
    ['Engineering Ratio', report.engineering_ratio ? `${report.engineering_ratio}%` : 'N/A'],
    ['Sales Ratio', report.sales_ratio ? `${report.sales_ratio}%` : 'N/A'],
    ['Funding Signals', fmtArr(report.funding_signals)],
    ['Recent Funding Round', report.recent_funding_round || 'N/A'],
    ['Valuation Estimate', report.valuation ? `$${report.valuation}` : 'N/A'],
    ['Total Raised', report.total_raised || 'N/A'],
    ['Burn Signals', fmtArr(report.burn_signals)],
    ['Growth Signals', fmtArr(report.growth_signals)],
  ];
  finFields.forEach(([k, v]) => drawFieldRow(doc, k, v, col1X, col1W, col2X, col2W));

  if (doc.y > doc.page.height - 160) doc.addPage();

  doc.moveDown(0.5);
  doc.fillColor(C.accentLt).fontSize(13).font('Helvetica-Bold').text('Financial Health Scores');
  doc.moveDown(0.3);

  const scoreX = doc.page.margins.left;
  const scoreW = doc.page.width - doc.page.margins.left - doc.page.margins.right;
  drawScoreGauge(doc, 'Financial Health', report.financial_health_score ?? 50, scoreX, doc.y, scoreW, C.emerald);
  doc.moveDown(1.2);
  drawScoreGauge(doc, 'Growth Signals Score', report.growth_score ?? 60, scoreX, doc.y, scoreW, C.cyan);
  doc.moveDown(1.2);

  if ((report.financial_health_score ?? 0) > 0 || (report.vitality_score ?? 0) > 0) {
    const chartData = [
      { label: 'Vitality', value: report.vitality_score ?? 70, color: C.cyan },
      { label: 'Financial Health', value: report.financial_health_score ?? 50, color: C.emerald },
      { label: 'Moat', value: report.moat_score ?? 60, color: C.accent },
      { label: 'Team Quality', value: report.team_quality_score ?? 70, color: C.pink },
    ].filter(d => d.value > 0);

    drawBarChart(doc, chartData, doc.page.margins.left, doc.y, doc.page.width - doc.page.margins.left - doc.page.margins.right, 150, 'Score Comparison');
  }
}

function drawMarketSection(doc: InstanceType<typeof PDFDocument>, report: Record<string, any>) {
  drawSectionHeader(doc, report.company_name, 'Market & Competitive Analysis');

  const col1X = doc.page.margins.left, col1W = 120, col2X = col1X + col1W, col2W = doc.page.width - doc.page.margins.right - col2X;
  const fmtArr = (v: any) => Array.isArray(v) ? v.join(', ') : (v || 'N/A');
  const marketFields = [
    ['Market Position', report.market_position || 'N/A'],
    ['Market Size', report.market_size_estimate || 'N/A'],
    ['Market Maturity', report.market_maturity || 'N/A'],
    ['Market Trends', fmtArr(report.market_trends)],
    ['Moat Type', report.competitive_moat?.type || report.moat_type || 'N/A'],
    ['Moat Strength', report.competitive_moat?.strength || report.moat_strength || 'N/A'],
    ['Differentiation', report.differentiation || 'N/A'],
    ['Winner Take All', report.winner_take_all?.toString() || 'N/A'],
    ['Substitution Risk', report.substitution_risk || 'N/A'],
    ['Barriers to Entry', fmtArr(report.barriers_to_entry)],
    ['Indirect Competitors', fmtArr(report.indirect_competitors)],
    ['Comparable Companies', fmtArr(report.comparable_companies)],
    ['Overall Sentiment', report.overall_sentiment || 'N/A'],
    ['Brand Perception', report.brand_perception || 'N/A'],
    ['Market Momentum', report.momentum || 'N/A'],
    ['Innovation Score', report.innovation_score?.toString() || 'N/A'],
  ];
  marketFields.forEach(([k, v]) => drawFieldRow(doc, k, v, col1X, col1W, col2X, col2W));

  doc.moveDown(0.5);
  const competitors = report.direct_competitors || [];
  if (competitors.length > 0) {
    if (doc.y > doc.page.height - 160) doc.addPage();
    doc.fillColor(C.accentLt).fontSize(13).font('Helvetica-Bold').text('Competitor Landscape');
    doc.moveDown(0.3);
    const compChartData = competitors.slice(0, 6).map((c: any, i: number) => ({
      label: typeof c === 'string' ? c : (c.name || c),
      value: typeof c === 'object' ? (c.similarity || c.threat_level === 'high' ? 85 : 60) : 70,
      color: C.chartColors[i % C.chartColors.length],
    }));
    drawBarChart(doc, compChartData, doc.page.margins.left, doc.y, doc.page.width - doc.page.margins.left - doc.page.margins.right, 140, 'Competitor Threat Comparison');
  }

  if (doc.y > doc.page.height - 180) doc.addPage();
  doc.moveDown(0.5);
  const riskPie = [
    { label: 'Competitive Risk', value: report.competitive_risk_score ?? 40, color: C.red },
    { label: 'Regulatory Risk', value: report.regulatory_risk_level === 'critical' ? 90 : report.regulatory_risk_level === 'high' ? 70 : report.regulatory_risk_level === 'medium' ? 50 : 20, color: C.amber },
    { label: 'Substitution Risk', value: report.substitution_risk === 'high' ? 75 : report.substitution_risk === 'medium' ? 50 : 25, color: C.pink },
    { label: 'Resilience', value: 100 - (report.competitive_risk_score ?? 40), color: C.emerald },
  ];
  drawPieChart(doc, riskPie, doc.page.width / 2, doc.y + 80, 60, 'Risk Distribution');
  doc.moveDown(7);
}

function drawChartsSection(doc: InstanceType<typeof PDFDocument>, report: Record<string, any>) {
  drawSectionHeader(doc, report.company_name, 'Data Visualization');

  const scoreItems = [
    { label: 'Vitality', value: report.vitality_score ?? 70, color: C.cyan },
    { label: 'Financial Health', value: report.financial_health_score ?? 50, color: C.emerald },
    { label: 'Team Quality', value: report.team_quality_score ?? 65, color: C.pink },
    { label: 'Compliance', value: report.compliance_score ?? 70, color: C.teal },
    { label: 'Moat', value: report.moat_score ?? 60, color: C.accent },
    { label: 'Risk', value: 100 - (report.risk_score ?? 40), color: C.amber },
    { label: 'Sentiment', value: report.sentiment_score ?? 60, color: C.cyan },
    { label: 'Confidence', value: Math.round((report.confidence_score ?? 0.7) * 100), color: C.emerald },
  ];
  drawBarChart(doc, scoreItems, doc.page.margins.left, doc.y, doc.page.width - doc.page.margins.left - doc.page.margins.right, 160, 'Overall Score Comparison');

  doc.moveDown(4);
  const sentimentPie = [
    { label: 'Strong Buy', value: 30, color: C.emerald },
    { label: 'Buy', value: 25, color: C.teal },
    { label: 'Hold', value: 20, color: C.amber },
    { label: 'Watch', value: 15, color: C.pink },
    { label: 'Avoid', value: 10, color: C.red },
  ];
  drawPieChart(doc, sentimentPie, doc.page.width / 2, doc.y + 100, 65, 'Sentiment Distribution');

  doc.moveDown(5);
  const riskScore = report.risk_score ?? 40;
  const oppScore = 100 - riskScore;
  const histoData = [
    { label: 'Opportunity', value: oppScore, color: C.emerald },
    { label: 'Risk', value: riskScore, color: C.red },
    { label: 'Resilience', value: Math.round((oppScore + (report.moat_score ?? 60)) / 2), color: C.accent },
  ];
  drawBarChart(doc, histoData, doc.page.margins.left, doc.y, doc.page.width - doc.page.margins.left - doc.page.margins.right, 130, 'Opportunity vs Risk Profile');
}

function buildPDF(report: Record<string, any>): Promise<Buffer> {
  return new Promise(async (resolve, reject) => {
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
    doc.on('end', () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);

    const logoUrl = report.logo_url || '';
    const logoBuffer = logoUrl ? await fetchImageAsBuffer(logoUrl) : null;

    // Cover page
    doc.addPage({ size: 'A4' });
    drawCoverPage(doc, report.company_name || report.target_url || 'Unknown', report.target_url || '', report.final_verdict || 'hold', {
      vitality: report.vitality_score ?? 0,
      moat: report.moat_score ?? 0,
      risk: report.risk_score ?? 0,
      confidence: report.confidence_score ?? 0.75,
    });

    // All subsequent pages get header via pageAdded
    doc.on('pageAdded', () => {
      doc.rect(0, 0, doc.page.width, doc.page.height).fill(C.bg);
      doc.rect(0, 0, doc.page.width, 36).fill(C.surface);
      doc.fillColor(C.accentLt).fontSize(8).font('Helvetica-Bold').text('AEGIS INTELLIGENCE', 50, 13);
      doc.fillColor(C.textMuted).fontSize(8).text(report.company_name || report.target_url || '', 0, 13, { align: 'right', width: doc.page.width - 50 });
      doc.moveTo(0, 36).lineTo(doc.page.width, 36).strokeColor(C.accent).lineWidth(0.5).stroke();
      doc.y = 50;
    });

    const safeDraw = (name: string, fn: () => void) => {
      try { fn(); } catch (e: any) { console.error(`[PDF] ${name} failed:`, e.message); }
    };

    // Each section starts a new page
    doc.addPage();
    safeDraw('Company Overview', () => drawCompanyOverview(doc, report, logoBuffer));

    doc.addPage();
    safeDraw('Leadership Section', () => drawLeadershipSection(doc, report));

    doc.addPage();
    safeDraw('Financial Section', () => drawFinancialSection(doc, report));

    doc.addPage();
    safeDraw('Market Section', () => drawMarketSection(doc, report));

    doc.addPage();
    safeDraw('Charts Section', () => drawChartsSection(doc, report));

    safeDraw('Full Markdown Report', () => {
      if (report.raw_markdown) {
        doc.addPage();
        doc.y = 50;
        doc.fillColor(C.accentLt).fontSize(20).font('Helvetica-Bold').text('Detailed Analysis');
        doc.moveDown(0.3);
        doc.moveTo(doc.page.margins.left, doc.y).lineTo(doc.page.width - doc.page.margins.right, doc.y).strokeColor(C.accent).lineWidth(0.5).stroke();
        doc.moveDown(0.5);
        renderMarkdownToPDF(doc, report.raw_markdown);
      }
    });

    doc.end();
  });
}

export async function reportRoutes(fastify: FastifyInstance) {

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

  fastify.get('/:investigationId/pdf', async (req, reply) => {
    const { investigationId } = req.params as { investigationId: string };
    const report = await queryOne(
      `SELECT r.*, i.target_url, i.company_name, r.final_verdict,
              i.vitality_score, i.moat_score, i.risk_score, i.confidence_score,
              r.metadata
       FROM reports r
       JOIN investigations i ON r.investigation_id = i.id
       WHERE r.investigation_id = $1`,
      [investigationId]
    );
    if (!report) return reply.status(404).send({ error: 'No report found' });
    const meta = report.metadata || {};
    Object.assign(report, meta);
    let pdfBuffer: Buffer;
    try {
      pdfBuffer = await buildPDF(report);
    } catch (err: any) {
      fastify.log.error({ err, investigationId }, 'PDF generation failed');
      return reply.status(500).send({ error: 'PDF generation failed', detail: err.stack || err.message });
    }
    const filename = `aegis-report-${(report.company_name || investigationId).toLowerCase().replace(/\s+/g, '-')}.pdf`;
    reply.header('Content-Type', 'application/pdf');
    reply.header('Content-Disposition', `attachment; filename="${filename}"`);
    reply.header('Content-Length', pdfBuffer.length);
    return reply.send(pdfBuffer);
  });

  // POST /reports/:investigationId/share — share PDF via email
  fastify.post('/:investigationId/share', async (req, reply) => {
    const { investigationId } = req.params as { investigationId: string };
    const { email, subject, message } = req.body as { email?: string; subject?: string; message?: string };

    const report = await queryOne(
      `SELECT r.*, i.target_url, i.company_name, r.final_verdict,
              i.vitality_score, i.moat_score, i.risk_score, i.confidence_score,
              r.metadata
       FROM reports r
       JOIN investigations i ON r.investigation_id = i.id
       WHERE r.investigation_id = $1`,
      [investigationId]
    );

    if (!report) return reply.status(404).send({ error: 'No report found' });

    // Merge metadata fields into report for PDF rendering
    const meta = report.metadata || {};
    Object.assign(report, meta);

    let pdfBuffer: Buffer;
    try {
      pdfBuffer = await buildPDF(report);
    } catch (err: any) {
      fastify.log.error({ err, investigationId }, 'PDF generation failed');
      return reply.status(500).send({ error: 'PDF generation failed', detail: err.stack || err.message });
    }

    const results: string[] = [];

    // Email share
    if (email) {
      try {
        const transporter = nodemailer.createTransport({
          host: process.env.SMTP_HOST || 'smtp.gmail.com',
          port: parseInt(process.env.SMTP_PORT || '587'),
          secure: process.env.SMTP_SECURE === 'true',
          auth: {
            user: process.env.SMTP_USER,
            pass: process.env.SMTP_PASS,
          },
        });
        await transporter.sendMail({
          from: process.env.SMTP_FROM || 'aegis@aegis.ai',
          to: email,
          subject: subject || `AEGIS Report: ${report.company_name || investigationId}`,
          text: message || `Please find attached the AEGIS strategic intelligence report for ${report.company_name || investigationId}.`,
          attachments: [{
            filename: `aegis-report-${(report.company_name || investigationId).toLowerCase().replace(/\s+/g, '-')}.pdf`,
            content: pdfBuffer,
          }],
        });
        results.push(`Email sent to ${email}`);
      } catch (err: any) {
        return reply.status(500).send({ error: `Failed to send email: ${err.message}` });
      }
    }

    // Native share — return PDF buffer for client-side native sharing (AirDrop, Bluetooth, etc.)
    if (!email) {
      const filename = `aegis-report-${(report.company_name || investigationId).toLowerCase().replace(/\s+/g, '-')}.pdf`;
      reply.header('Content-Type', 'application/pdf');
      reply.header('Content-Disposition', `attachment; filename="${filename}"`);
      reply.header('Content-Length', pdfBuffer.length);
      return reply.send(pdfBuffer);
    }

    return reply.send({ success: true, results });
  });
}
