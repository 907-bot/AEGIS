'use client';
import { useEffect, useState, useRef } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain, Shield, TrendingUp, TrendingDown, AlertTriangle, CheckCircle2,
  Clock, Zap, BarChart3, Network, FileText, ChevronDown, ChevronUp,
  Target, Globe, Users, Code2, Newspaper, Scale, Swords, RefreshCw,
  Download, FileDown, Loader2, Share2, ExternalLink, DollarSign, Activity
} from 'lucide-react';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';
import { createSocket } from '@/lib/socket';
import { ScoreRing } from '@/components/ui/ScoreRing';
import { AgentCard } from '@/components/agents/AgentCard';
import { DebateChamber } from '@/components/agents/DebateChamber';
import { KnowledgeGraph } from '@/components/graph/KnowledgeGraph';
import { RedFlagMatrix } from '@/components/ui/RedFlagMatrix';
import { ScenarioSimulator } from '@/components/charts/ScenarioSimulator';
import { MoatRadar } from '@/components/charts/MoatRadar';

const AGENT_META: Record<string, { icon: any; color: string; label: string }> = {
  sentry:                  { icon: Globe,   color: 'text-cyan-400',    label: 'Sentry' },
  financial_archaeologist: { icon: BarChart3,color: 'text-emerald-400', label: 'Financial' },
  talent_flow:             { icon: Users,   color: 'text-violet-400',  label: 'Talent' },
  tech_stack:              { icon: Code2,   color: 'text-blue-400',    label: 'Tech Stack' },
  sentiment_scout:         { icon: Newspaper,color:'text-amber-400',   label: 'Sentiment' },
  regulatory_radar:        { icon: Scale,   color: 'text-red-400',     label: 'Regulatory' },
  competitive_cartographer:{ icon: Swords,  color: 'text-pink-400',    label: 'Competitive' },
};

const VERDICT_STYLE: Record<string, { bg: string; text: string; border: string }> = {
  strong_buy: { bg: 'bg-emerald-500/20', text: 'text-emerald-300', border: 'border-emerald-500/40' },
  buy:        { bg: 'bg-green-500/20',   text: 'text-green-300',   border: 'border-green-500/40' },
  hold:       { bg: 'bg-amber-500/20',   text: 'text-amber-300',   border: 'border-amber-500/40' },
  watch:      { bg: 'bg-orange-500/20',  text: 'text-orange-300',  border: 'border-orange-500/40' },
  avoid:      { bg: 'bg-red-500/20',     text: 'text-red-300',     border: 'border-red-500/40' },
};

type AgentEvent = {
  agentType: string; status: string; currentAction: string;
  confidence: number; evidenceCount: number; timestamp: string; latencyMs: number;
};

type InvestigationData = {
  id: string; target_url: string; company_name?: string; status: string;
  investigation_type?: string;
  confidence_score?: number; vitality_score?: number; moat_score?: number;
  risk_score?: number; executive_summary?: string; bull_thesis?: string;
  bear_thesis?: string; skeptic_analysis?: string; final_verdict?: string;
  red_flag_matrix?: any[]; moat_analysis?: any; scenarios?: any;
  recommendations?: any[]; comparable_companies?: string[];
  valuation_comps?: any[];
  unit_economics?: any;
  traffic_metrics?: any;
  evidence_citations?: any[];
};

export default function InvestigationClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const id = searchParams.get('id') || '';
  const [inv, setInv]           = useState<InvestigationData | null>(null);
  const [events, setEvents]     = useState<AgentEvent[]>([]);
  const [activeTab, setActiveTab] = useState<'overview'|'debate'|'graph'|'simulate'>('overview');
  const [graphData, setGraphData] = useState<{ nodes: any[]; edges: any[] } | null>(null);
  const [polling, setPolling]       = useState(true);
  const [apiError, setApiError]     = useState<string | null>(null);
  const [stuck, setStuck]           = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const socketRef                   = useRef<any>(null);
  const pollRef                     = useRef<NodeJS.Timeout | null>(null);
  const startTimeRef                = useRef<number>(Date.now());

  // ── Load investigation ──────────────────────────────────────────────────
  const loadInv = async () => {
    try {
      const res = await api.get(`/api/v1/investigations/${id}`);
      setApiError(null);
      setInv(res.data);
      if (['completed', 'failed'].includes(res.data.status)) {
        setPolling(false);
        loadGraph();
      }
      // Show warning if stuck in queued for > 30s
      if (res.data.status === 'queued' && Date.now() - startTimeRef.current > 30000) {
        setStuck(true);
      }
    } catch (err: any) {
      const msg = err.response?.data?.error || err.message || 'Connection lost';
      setApiError(msg);
      if (Date.now() - startTimeRef.current > 15000) {
        toast.error(`Backend unreachable: ${msg}`);
      }
    }
  };

  const loadGraph = async () => {
    try {
      const res = await api.get(`/api/v1/investigations/${id}/graph-data`);
      setGraphData(res.data);
    } catch (_) {}
  };

  const retryInvestigation = async () => {
    if (!inv) return;
    try {
      const res = await api.post('/api/v1/investigations', {
        url: inv.target_url,
        type: inv.investigation_type || 'competitive',
      });
      toast.success('Investigation re-launched');
      if (res.data?.investigationId && res.data.investigationId !== id) {
        router.push(`/investigation?id=${res.data.investigationId}`);
      } else {
        startTimeRef.current = Date.now();
        setStuck(false);
        setPolling(true);
      }
    } catch {
      toast.error('Failed to re-launch');
    }
  };

  const downloadPDF = async () => {
    if (!inv || pdfLoading) return;
    setPdfLoading(true);
    try {
      const res = await api.get(`/api/v1/reports/${inv.id}/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `aegis-report-${(inv.company_name || inv.id).toLowerCase().replace(/\s+/g, '-')}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('PDF downloaded');
    } catch {
      toast.error('PDF generation failed. Try again.');
    } finally {
      setPdfLoading(false);
    }
  };

  const downloadMarkdown = async () => {
    if (!inv) return;
    try {
      const res = await api.get(`/api/v1/reports/${inv.id}/markdown`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'text/markdown' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `aegis-report-${(inv.company_name || inv.id).toLowerCase().replace(/\s+/g, '-')}.md`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Markdown downloaded');
    } catch {
      toast.error('Failed to download markdown.');
    }
  };

  const sharePDF = async () => {
    if (!inv || pdfLoading) return;
    setPdfLoading(true);
    try {
      const res = await api.get(`/api/v1/reports/${inv.id}/pdf`, { responseType: 'blob' });
      const blob = new Blob([res.data], { type: 'application/pdf' });
      const filename = `aegis-report-${(inv.company_name || inv.id).toLowerCase().replace(/\s+/g, '-')}.pdf`;

      // Try Web Share API first (AirDrop, Bluetooth, nearby sharing, etc.)
      if (navigator.share && navigator.canShare) {
        const file = new File([blob], filename, { type: 'application/pdf' });
        const shareData = { files: [file], title: `AEGIS Report: ${inv.company_name || inv.id}` };
        if (navigator.canShare(shareData)) {
          await navigator.share(shareData);
          toast.success('Shared successfully');
          setPdfLoading(false);
          return;
        }
      }

      // Fallback: download the PDF
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('PDF downloaded (share not supported on this device)');
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        toast.error('Share failed. Try again.');
      }
    } finally {
      setPdfLoading(false);
    }
  };

  // ── Polling ─────────────────────────────────────────────────────────────
  useEffect(() => {
    startTimeRef.current = Date.now();
    loadInv();
    if (polling) {
      pollRef.current = setInterval(loadInv, 4000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [id, polling]);

  // ── Socket.IO real-time events ──────────────────────────────────────────
  useEffect(() => {
    const socket = createSocket();
    socketRef.current = socket;
    socket.emit('subscribe:investigation', id);
    socket.on('agent:event', (event: AgentEvent) => {
      setEvents(prev => [...prev.slice(-200), event]);
    });
    return () => { socket.disconnect(); };
  }, [id]);

  if (!inv) return <LoadingScreen />;

  const isRunning   = inv.status === 'running' || inv.status === 'queued';
  const isCompleted = inv.status === 'completed';
  const verdict     = inv.final_verdict || 'hold';
  const vStyle      = VERDICT_STYLE[verdict] || VERDICT_STYLE.hold;

  // Agent states derived from events
  const agentStates = Object.keys(AGENT_META).reduce((acc, k) => {
    const agentEvents = events.filter(e => e.agentType === k);
    const last = agentEvents[agentEvents.length - 1];
    acc[k] = last || null;
    return acc;
  }, {} as Record<string, AgentEvent | null>);

  const completedCount = Object.values(agentStates).filter(e => e?.status === 'completed').length;
  const progress = isCompleted ? 100 : isRunning ? Math.max(5, (completedCount / 7) * 80) : 0;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-slate-800 px-6 py-4 backdrop-blur-sm bg-surface/80 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" prefetch={false} className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors">
              <Brain className="w-5 h-5 text-aegis-400" />
              <span className="font-bold">AEGIS</span>
            </Link>
            <span className="text-slate-600">/</span>
            <div>
              <div className="font-semibold text-sm truncate max-w-xs">
                {inv.company_name || inv.target_url}
              </div>
              <div className="text-xs text-slate-500">{inv.target_url}</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status={inv.status} />
            {isCompleted && (
              <>
                <span className={`badge border px-3 py-1 text-sm font-semibold ${vStyle.bg} ${vStyle.text} ${vStyle.border}`}>
                  {verdict.toUpperCase().replace('_',' ')}
                </span>
                <button
                  id="btn-download-markdown"
                  onClick={downloadMarkdown}
                  title="Export Markdown"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                             text-slate-300 bg-slate-800 border border-slate-700
                             hover:bg-slate-700 hover:border-slate-600 hover:text-white
                             transition-all duration-150"
                >
                  <FileDown className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">.md</span>
                </button>
                <button
                  id="btn-download-pdf"
                  onClick={downloadPDF}
                  disabled={pdfLoading}
                  title="Download PDF Report"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                             text-white bg-indigo-600 border border-indigo-500
                             hover:bg-indigo-500 disabled:opacity-60 disabled:cursor-not-allowed
                             transition-all duration-150 shadow-lg shadow-indigo-900/40"
                >
                  {pdfLoading
                    ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    : <Download className="w-3.5 h-3.5" />}
                  <span className="hidden sm:inline">{pdfLoading ? 'Generating…' : 'PDF'}</span>
                </button>
                <button
                  id="btn-share-pdf"
                  onClick={sharePDF}
                  disabled={pdfLoading}
                  title="Share PDF (AirDrop, Bluetooth, etc.)"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                             text-slate-300 bg-slate-800 border border-slate-700
                             hover:bg-slate-700 hover:border-slate-600 hover:text-white
                             disabled:opacity-60 disabled:cursor-not-allowed
                             transition-all duration-150"
                >
                  <Share2 className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Share</span>
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      <div className="flex-1 max-w-7xl mx-auto w-full px-6 py-8">
        {/* Progress bar */}
        {apiError && (
          <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>Connection error: {apiError}</span>
          </div>
        )}
        {stuck && inv?.status === 'queued' && (
          <div className="mb-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-sm">
            <div className="flex items-center gap-2 mb-1">
              <Clock className="w-4 h-4 shrink-0" />
              <span>Investigation is taking longer than expected. The backend may need a moment to start up.</span>
            </div>
            <button onClick={retryInvestigation} className="mt-2 text-xs underline hover:text-amber-200">
              Click to retry
            </button>
          </div>
        )}
        {isRunning && (
          <div className="mb-6">
            <div className="flex justify-between text-xs text-slate-500 mb-2">
              <span>Investigating... {completedCount}/7 agents complete</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-aegis-600 to-indigo-500 rounded-full"
                initial={{ width: '5%' }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.5 }}
              />
            </div>
          </div>
        )}

        {/* Score cards */}
        {isCompleted && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <ScoreRing label="Vitality" score={inv.vitality_score ?? 0} color="cyan"    />
            <ScoreRing label="Moat"     score={inv.moat_score ?? 0}     color="indigo"  />
            <ScoreRing label="Risk"     score={inv.risk_score ?? 0}      color="red"     inverted />
            <ScoreRing label="Confidence" score={Math.round((inv.confidence_score ?? 0) * 100)} color="emerald" />
          </div>
        )}

        {/* Two-column layout */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Left: Agent Stream */}
          <div className="lg:col-span-1 space-y-4">
            <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
              <Zap className="w-4 h-4 text-aegis-400" /> Agent Activity
            </h3>
            <div className="space-y-2">
              {Object.entries(AGENT_META).map(([key, meta]) => (
                <AgentCard
                  key={key}
                  agentKey={key}
                  meta={meta}
                  event={agentStates[key]}
                />
              ))}
            </div>

            {/* Live event log */}
            {events.length > 0 && (
              <div className="card p-4">
                <div className="text-xs font-semibold text-slate-500 uppercase mb-3">Live Log</div>
                <div className="space-y-1.5 max-h-48 overflow-y-auto">
                  {events.slice(-20).reverse().map((e, i) => (
                    <div key={i} className="flex gap-2 text-xs">
                      <span className="text-slate-600 font-mono shrink-0">
                        {new Date(e.timestamp).toLocaleTimeString()}
                      </span>
                      <span className={AGENT_META[e.agentType]?.color || 'text-slate-400'}>
                        [{AGENT_META[e.agentType]?.label || e.agentType}]
                      </span>
                      <span className="text-slate-400 truncate">{e.currentAction}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right: Report tabs */}
          <div className="lg:col-span-2">
            {isRunning && <AnalysingPlaceholder />}

            {isCompleted && (
              <>
                {/* Tabs */}
                <div className="flex gap-1 mb-6 p-1 bg-surface-50 rounded-xl border border-slate-700">
                  {([
                    { id: 'overview', label: 'Overview',   icon: FileText  },
                    { id: 'debate',   label: 'Debate',     icon: Swords    },
                    { id: 'graph',    label: 'Graph',      icon: Network   },
                    { id: 'simulate', label: 'Simulate',   icon: BarChart3 },
                  ] as const).map(tab => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                        activeTab === tab.id
                          ? 'bg-aegis-600 text-white shadow-lg'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      <tab.icon className="w-4 h-4" />
                      <span className="hidden sm:inline">{tab.label}</span>
                    </button>
                  ))}
                </div>

                <AnimatePresence mode="wait">
                  {activeTab === 'overview' && (
                    <motion.div key="overview" initial={{ opacity:0,y:8 }} animate={{ opacity:1,y:0 }} exit={{ opacity:0 }}>
                      <OverviewTab inv={inv} />
                    </motion.div>
                  )}
                  {activeTab === 'debate' && (
                    <motion.div key="debate" initial={{ opacity:0,y:8 }} animate={{ opacity:1,y:0 }} exit={{ opacity:0 }}>
                      <DebateChamber inv={inv} />
                    </motion.div>
                  )}
                  {activeTab === 'graph' && (
                    <motion.div key="graph" initial={{ opacity:0,y:8 }} animate={{ opacity:1,y:0 }} exit={{ opacity:0 }}>
                      <KnowledgeGraph data={graphData} investigationId={id || ''} />
                    </motion.div>
                  )}
                  {activeTab === 'simulate' && (
                    <motion.div key="simulate" initial={{ opacity:0,y:8 }} animate={{ opacity:1,y:0 }} exit={{ opacity:0 }}>
                      <ScenarioSimulator investigationId={id || ''} baseScores={{
                        vitality: inv.vitality_score ?? 50,
                        moat:     inv.moat_score ?? 50,
                        risk:     inv.risk_score ?? 50,
                      }} />
                    </motion.div>
                  )}
                </AnimatePresence>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────
function OverviewTab({ inv }: { inv: InvestigationData }) {
  const comps = inv.valuation_comps || [];
  const unitEcon = inv.unit_economics;
  const traffic = inv.traffic_metrics;
  const citations = inv.evidence_citations || [];

  return (
    <div className="space-y-6">
      {/* Executive Summary */}
      {inv.executive_summary && (
        <div className="card p-6">
          <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">Executive Summary</h3>
          <p className="text-slate-200 leading-relaxed">{inv.executive_summary}</p>
        </div>
      )}

      {/* Real-World Parameters: Unit Economics & Rule of 40 */}
      {unitEcon && <UnitEconomicsCard unitEcon={unitEcon} />}

      {/* Real-World Parameters: Trading Comps & Valuation Multiples */}
      {comps.length > 0 && <ValuationCompsCard comps={comps} />}

      {/* Real-World Parameters: Digital Footprint & Web Traffic */}
      {traffic && <TrafficRadarCard traffic={traffic} />}

      {/* Red Flags */}
      {inv.red_flag_matrix && inv.red_flag_matrix.length > 0 && (
        <RedFlagMatrix flags={inv.red_flag_matrix} />
      )}

      {/* Moat + Recommendations */}
      <div className="grid md:grid-cols-2 gap-4">
        {inv.moat_analysis && <MoatRadar moat={inv.moat_analysis} />}
        {inv.recommendations && inv.recommendations.length > 0 && (
          <div className="card p-5">
            <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Recommendations</h3>
            <div className="space-y-3">
              {inv.recommendations.slice(0, 4).map((r: any, i: number) => (
                <div key={i} className="flex gap-3">
                  <span className={`badge shrink-0 ${
                    r.priority === 'immediate' ? 'badge-danger' :
                    r.priority === 'short_term' ? 'badge-warning' : 'badge-neutral'
                  }`}>{r.priority?.replace('_',' ')}</span>
                  <div>
                    <div className="text-sm font-medium">{r.action}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{r.rationale}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Real-World Features: Evidence & Source Citation Audit Trail */}
      {citations.length > 0 && <EvidenceCitationsCard citations={citations} />}

      {/* Comparable companies */}
      {inv.comparable_companies && inv.comparable_companies.length > 0 && (
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">Comparable Companies</h3>
          <div className="flex flex-wrap gap-2">
            {inv.comparable_companies.map((c, i) => (
              <span key={i} className="badge badge-neutral">{c}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function UnitEconomicsCard({ unitEcon }: { unitEcon: any }) {
  const rule40 = Number(unitEcon.rule_of_40_score ?? 0);
  const rule40Color = rule40 >= 40 ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' :
                      rule40 >= 20 ? 'text-amber-400 bg-amber-500/10 border-amber-500/30' :
                      'text-red-400 bg-red-500/10 border-red-500/30';

  return (
    <div className="card p-6 border-slate-800">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
            SaaS Unit Economics & Rule of 40
          </h3>
        </div>
        <div className={`px-3 py-1 rounded-full text-xs font-semibold border flex items-center gap-1.5 ${rule40Color}`}>
          <span>Rule of 40:</span>
          <span className="font-bold">{rule40 > 0 ? `+${rule40}` : rule40}%</span>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-surface/50 p-3 rounded-lg border border-slate-800/80">
          <div className="text-xs text-slate-500">ARR Run-Rate</div>
          <div className="text-base font-bold text-slate-200 mt-1">{unitEcon.arr_estimate || 'N/A'}</div>
        </div>
        <div className="bg-surface/50 p-3 rounded-lg border border-slate-800/80">
          <div className="text-xs text-slate-500">YoY Growth</div>
          <div className="text-base font-bold text-emerald-400 mt-1">
            {unitEcon.revenue_growth_yoy ? `+${unitEcon.revenue_growth_yoy}%` : 'N/A'}
          </div>
        </div>
        <div className="bg-surface/50 p-3 rounded-lg border border-slate-800/80">
          <div className="text-xs text-slate-500">FCF Margin</div>
          <div className={`text-base font-bold mt-1 ${Number(unitEcon.free_cash_flow_margin) >= 0 ? 'text-emerald-400' : 'text-amber-400'}`}>
            {unitEcon.free_cash_flow_margin !== undefined ? `${unitEcon.free_cash_flow_margin}%` : 'N/A'}
          </div>
        </div>
        <div className="bg-surface/50 p-3 rounded-lg border border-slate-800/80">
          <div className="text-xs text-slate-500">Gross Margin</div>
          <div className="text-base font-bold text-slate-200 mt-1">
            {unitEcon.gross_margin_percent ? `${unitEcon.gross_margin_percent}%` : 'N/A'}
          </div>
        </div>
        <div className="bg-surface/50 p-3 rounded-lg border border-slate-800/80">
          <div className="text-xs text-slate-500">Net Dollar Retention</div>
          <div className="text-base font-bold text-cyan-400 mt-1">
            {unitEcon.net_dollar_retention ? `${unitEcon.net_dollar_retention}%` : 'N/A'}
          </div>
        </div>
        <div className="bg-surface/50 p-3 rounded-lg border border-slate-800/80">
          <div className="text-xs text-slate-500">CAC Payback</div>
          <div className="text-base font-bold text-slate-200 mt-1">
            {unitEcon.cac_payback_months ? `${unitEcon.cac_payback_months} mos` : 'N/A'}
          </div>
        </div>
        <div className="bg-surface/50 p-3 rounded-lg border border-slate-800/80">
          <div className="text-xs text-slate-500">LTV / CAC Ratio</div>
          <div className="text-base font-bold text-indigo-400 mt-1">
            {unitEcon.ltv_cac_ratio ? `${unitEcon.ltv_cac_ratio}x` : 'N/A'}
          </div>
        </div>
        <div className="bg-surface/50 p-3 rounded-lg border border-slate-800/80">
          <div className="text-xs text-slate-500">Capital Efficiency</div>
          <div className="text-base font-bold text-emerald-400 mt-1">
            {rule40 >= 40 ? 'Elite (Top Tier)' : rule40 >= 20 ? 'Standard' : 'Burn Heavy'}
          </div>
        </div>
      </div>
    </div>
  );
}

function ValuationCompsCard({ comps }: { comps: any[] }) {
  return (
    <div className="card p-6 border-slate-800">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
            Trading Comps & Valuation Multiples
          </h3>
        </div>
        <span className="text-xs text-slate-500">Institutional Benchmarks</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold">
              <th className="py-2.5 px-3">Peer Company</th>
              <th className="py-2.5 px-3">Ticker</th>
              <th className="py-2.5 px-3">EV / ARR</th>
              <th className="py-2.5 px-3">P / E Multiple</th>
              <th className="py-2.5 px-3">EV / EBITDA</th>
              <th className="py-2.5 px-3">Implied Valuation</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {comps.map((c, i) => (
              <tr key={i} className="hover:bg-surface-50/50 transition-colors">
                <td className="py-2.5 px-3 font-sans font-medium text-slate-200">{c.name || 'Peer'}</td>
                <td className="py-2.5 px-3 text-cyan-400">{c.ticker || 'N/A'}</td>
                <td className="py-2.5 px-3 text-emerald-400">{c.ev_arr || 'N/A'}</td>
                <td className="py-2.5 px-3 text-slate-300">{c.pe_multiple || 'N/A'}</td>
                <td className="py-2.5 px-3 text-slate-300">{c.ev_ebitda || 'N/A'}</td>
                <td className="py-2.5 px-3 font-semibold text-indigo-300">{c.implied_valuation || 'N/A'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TrafficRadarCard({ traffic }: { traffic: any }) {
  return (
    <div className="card p-6 border-slate-800">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
            Digital Footprint & Web Traffic Radar
          </h3>
        </div>
        <span className="text-xs text-slate-500">Autonomous Web Signal</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <div className="bg-surface/50 p-3 rounded-lg border border-slate-800/80">
          <div className="text-xs text-slate-500">Monthly Traffic</div>
          <div className="text-base font-bold text-slate-200 mt-1">{traffic.monthly_visits || 'N/A'}</div>
        </div>
        <div className="bg-surface/50 p-3 rounded-lg border border-slate-800/80">
          <div className="text-xs text-slate-500">MoM Growth</div>
          <div className="text-base font-bold text-emerald-400 mt-1">
            {traffic.mom_growth_percent ? `+${traffic.mom_growth_percent}%` : 'N/A'}
          </div>
        </div>
        <div className="bg-surface/50 p-3 rounded-lg border border-slate-800/80">
          <div className="text-xs text-slate-500">Bounce Rate</div>
          <div className="text-base font-bold text-slate-200 mt-1">
            {traffic.bounce_rate_percent ? `${traffic.bounce_rate_percent}%` : 'N/A'}
          </div>
        </div>
        <div className="bg-surface/50 p-3 rounded-lg border border-slate-800/80">
          <div className="text-xs text-slate-500">Avg Duration</div>
          <div className="text-base font-bold text-cyan-400 mt-1">
            {traffic.avg_session_duration_sec ? `${traffic.avg_session_duration_sec}s` : 'N/A'}
          </div>
        </div>
      </div>

      {traffic.top_geographies && (
        <div className="flex flex-wrap items-center gap-2 text-xs pt-1 border-t border-slate-800/80">
          <span className="text-slate-500">Top Markets:</span>
          {(Array.isArray(traffic.top_geographies) ? traffic.top_geographies : [traffic.top_geographies]).map((geo: string, idx: number) => (
            <span key={idx} className="badge badge-neutral text-xs">{geo}</span>
          ))}
          {traffic.organic_search_percent && (
            <span className="badge badge-info text-xs ml-auto">
              {traffic.organic_search_percent}% Organic Traffic
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function EvidenceCitationsCard({ citations }: { citations: any[] }) {
  return (
    <div className="card p-6 border-slate-800">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
            Evidence & Source Citations Audit Trail
          </h3>
        </div>
        <span className="text-xs text-slate-500">{citations.length} verified sources</span>
      </div>

      <div className="space-y-3">
        {citations.map((c, i) => (
          <div key={i} className="p-3 rounded-lg bg-surface/60 border border-slate-800/90 text-xs">
            <div className="flex items-center justify-between gap-2 mb-1.5">
              <div className="font-semibold text-slate-200 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />
                <span>{c.claim || 'Verified Data Point'}</span>
              </div>
              {c.source_url && (
                <a
                  href={c.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-aegis-400 hover:text-aegis-300 flex items-center gap-1 font-mono shrink-0 hover:underline"
                >
                  <span>Source</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
            {c.snippet && (
              <p className="text-slate-400 font-mono text-[11px] leading-relaxed border-l-2 border-slate-700 pl-2.5 my-1">
                "{c.snippet}"
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    queued:    'badge-neutral',
    running:   'badge-info',
    completed: 'badge-success',
    failed:    'badge-danger',
  };
  return (
    <span className={`badge ${styles[status] || 'badge-neutral'}`}>
      {status === 'running' && <span className="w-1.5 h-1.5 bg-aegis-400 rounded-full animate-pulse" />}
      {status}
    </span>
  );
}

function AnalysingPlaceholder() {
  return (
    <div className="card p-12 flex flex-col items-center justify-center text-center">
      <div className="w-16 h-16 rounded-2xl bg-aegis-600/20 flex items-center justify-center mb-4 animate-pulse">
        <Brain className="w-8 h-8 text-aegis-400" />
      </div>
      <h3 className="font-semibold text-lg mb-2">Agents are working...</h3>
      <p className="text-slate-500 text-sm max-w-sm">
        All 7 agents are simultaneously gathering intelligence. The debate chamber
        will open once reconnaissance is complete.
      </p>
    </div>
  );
}

function LoadingScreen() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <Brain className="w-10 h-10 text-aegis-400 animate-spin-slow" />
        <p className="text-slate-500">Loading investigation...</p>
      </div>
    </div>
  );
}
