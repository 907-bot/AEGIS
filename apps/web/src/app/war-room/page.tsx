'use client';
import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, Zap, Activity, Globe, TrendingUp, BarChart3, Radio } from 'lucide-react';
import Link from 'next/link';
import { createSocket } from '@/lib/socket';
import { api } from '@/lib/api';

type LiveEvent = {
  investigationId: string; agentType: string; status: string;
  currentAction: string; confidence: number; timestamp: string;
};

const AGENT_COLORS: Record<string, string> = {
  sentry: 'text-cyan-400', financial_archaeologist: 'text-emerald-400',
  talent_flow: 'text-violet-400', tech_stack: 'text-blue-400',
  sentiment_scout: 'text-amber-400', regulatory_radar: 'text-red-400',
  competitive_cartographer: 'text-pink-400',
};

export default function WarRoomPage() {
  const [events, setEvents]           = useState<LiveEvent[]>([]);
  const [stats, setStats]             = useState<any>(null);
  const [connected, setConnected]     = useState(false);
  const [investigations, setInvestigations] = useState<any[]>([]);

  useEffect(() => {
    // Load dashboard stats
    api.get('/api/v1/analytics/dashboard').then(r => setStats(r.data.stats)).catch(() => {});
    api.get('/api/v1/investigations').then(r => setInvestigations(r.data.investigations?.slice(0,5) || [])).catch(() => {});

    const socket = createSocket();
    socket.emit('join:war-room');
    socket.on('connect',    () => setConnected(true));
    socket.on('disconnect', () => setConnected(false));
    socket.on('agent:event', (event: LiveEvent) => {
      setEvents(prev => [event, ...prev].slice(0, 500));
    });
    return () => { socket.disconnect(); };
  }, []);

  // Aggregate stats from live events
  const agentActivity = events.slice(0, 100).reduce((acc, e) => {
    acc[e.agentType] = (acc[e.agentType] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="min-h-screen flex flex-col bg-surface">
      {/* Header */}
      <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between bg-surface/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <Brain className="w-5 h-5 text-aegis-400" />
          <span className="font-bold">AEGIS</span>
          <span className="text-slate-600">/</span>
          <span className="text-slate-300 font-semibold flex items-center gap-2">
            <Radio className="w-4 h-4 text-red-400 animate-pulse" /> War Room
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-2 text-xs ${connected ? 'text-emerald-400' : 'text-red-400'}`}>
            <span className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
            {connected ? 'Live Feed Active' : 'Disconnected'}
          </div>
          <Link href="/dashboard" prefetch={false} className="btn-secondary text-sm">Dashboard</Link>
          <Link href="/" prefetch={false} className="btn-primary text-sm">New Investigation</Link>
        </div>
      </header>

      <div className="flex-1 grid grid-cols-12 gap-0 h-[calc(100vh-64px)]">
        {/* Left sidebar: Stats */}
        <div className="col-span-3 border-r border-slate-800 p-5 overflow-y-auto space-y-5">
          <div>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Platform Stats</h3>
            {stats && (
              <div className="space-y-3">
                {[
                  { label: 'Total Investigations', value: stats.total_investigations, color: 'text-aegis-400' },
                  { label: 'Completed',             value: stats.completed,           color: 'text-emerald-400' },
                  { label: 'Currently Running',     value: stats.running,             color: 'text-amber-400' },
                  { label: 'Avg Vitality Score',    value: parseFloat(stats.avg_vitality||'0').toFixed(1), color: 'text-blue-400' },
                ].map(s => (
                  <div key={s.label} className="card p-3">
                    <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
                    <div className="text-xs text-slate-500">{s.label}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Agent activity heat */}
          <div>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Agent Activity (last 100)</h3>
            <div className="space-y-2">
              {Object.entries(agentActivity).sort((a,b) => b[1]-a[1]).map(([agent, count]) => (
                <div key={agent} className="flex items-center gap-2">
                  <div className={`text-xs font-mono w-24 truncate ${AGENT_COLORS[agent] || 'text-slate-400'}`}>
                    {agent.replace('_',' ')}
                  </div>
                  <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-aegis-600 rounded-full transition-all"
                      style={{ width: `${(count / Math.max(...Object.values(agentActivity))) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-slate-600 w-6 text-right">{count}</span>
                </div>
              ))}
              {Object.keys(agentActivity).length === 0 && (
                <p className="text-xs text-slate-600">Waiting for activity...</p>
              )}
            </div>
          </div>

          {/* Recent investigations */}
          <div>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Recent</h3>
            <div className="space-y-2">
              {investigations.map(inv => (
                <Link
                  key={inv.id}
                  href={`/investigation/${inv.id}`}
                  prefetch={false}
                  className="card p-3 block hover:border-aegis-500/30 transition-colors"
                >
                  <div className="text-xs font-medium truncate">{inv.company_name || inv.target_url}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-xs ${inv.status === 'completed' ? 'text-emerald-400' : inv.status === 'running' ? 'text-amber-400' : 'text-slate-500'}`}>
                      {inv.status}
                    </span>
                    {inv.vitality_score && <span className="text-xs text-slate-600">{inv.vitality_score}/100</span>}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Center: Live feed */}
        <div className="col-span-6 border-r border-slate-800 flex flex-col">
          <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-aegis-400" />
              <span className="text-sm font-semibold">Live Intelligence Stream</span>
            </div>
            <span className="text-xs text-slate-500">{events.length} events</span>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-2 font-mono text-xs">
            <AnimatePresence initial={false}>
              {events.slice(0, 100).map((event, i) => (
                <motion.div
                  key={`${event.investigationId}-${event.timestamp}-${i}`}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="flex gap-3 items-start p-2 rounded-lg hover:bg-surface-50 transition-colors"
                >
                  <span className="text-slate-600 shrink-0 w-[70px]">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                  <span className={`shrink-0 w-[140px] ${AGENT_COLORS[event.agentType] || 'text-slate-400'}`}>
                    [{event.agentType?.replace(/_/g,' ')}]
                  </span>
                  <span className={`flex-1 ${
                    event.status === 'completed' ? 'text-emerald-300' :
                    event.status === 'failed'    ? 'text-red-300' :
                    'text-slate-300'
                  }`}>
                    {event.currentAction}
                  </span>
                  {event.confidence > 0 && (
                    <span className="text-slate-600 shrink-0">
                      {(event.confidence*100).toFixed(0)}%
                    </span>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
            {events.length === 0 && (
              <div className="text-slate-600 text-center py-20">
                Waiting for intelligence feed...<br />
                <span className="text-slate-700">Start an investigation to see live agent activity</span>
              </div>
            )}
          </div>
        </div>

        {/* Right: Pulse monitor */}
        <div className="col-span-3 p-5 overflow-y-auto space-y-5">
          <div>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">System Pulse</h3>
            <div className="space-y-3">
              {[
                { label: 'API Gateway',       color: 'bg-emerald-400', status: 'Healthy' },
                { label: 'Agent Orchestrator',color: 'bg-emerald-400', status: 'Healthy' },
                { label: 'Go Gateway',        color: 'bg-emerald-400', status: 'Healthy' },
                { label: 'Redis Pub/Sub',     color: connected ? 'bg-emerald-400' : 'bg-red-400', status: connected ? 'Connected' : 'Disconnected' },
                { label: 'Neo4j Graph DB',    color: 'bg-emerald-400', status: 'Active' },
                { label: 'LLM Router',        color: 'bg-emerald-400', status: 'OpenAI + Anthropic' },
              ].map(s => (
                <div key={s.label} className="card p-3 flex items-center gap-3">
                  <span className={`w-2 h-2 rounded-full ${s.color} animate-pulse shrink-0`} />
                  <div>
                    <div className="text-xs font-medium">{s.label}</div>
                    <div className="text-xs text-slate-500">{s.status}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Quick Actions</h3>
            <div className="space-y-2">
              <Link href="/" prefetch={false} className="btn-primary w-full text-xs justify-center">
                <Zap className="w-3 h-3" /> New Investigation
              </Link>
              <Link href="/dashboard" prefetch={false} className="btn-secondary w-full text-xs justify-center">
                <BarChart3 className="w-3 h-3" /> Full Dashboard
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
