'use client';
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Brain, Plus, TrendingUp, Clock, CheckCircle2, AlertCircle, Search, Filter } from 'lucide-react';
import { api } from '@/lib/api';
import Link from 'next/link';

type Investigation = {
  id: string; target_url: string; company_name?: string;
  investigation_type: string; status: string;
  confidence_score?: number; vitality_score?: number;
  created_at: string; duration_ms?: number;
};

type Stats = {
  total_investigations: string; completed: string; running: string;
  avg_confidence: string; avg_vitality: string; avg_duration_ms: string; total_cost: string;
};

const STATUS_COLORS: Record<string, string> = {
  queued:    'badge-neutral', running: 'badge-info',
  completed: 'badge-success', failed:  'badge-danger',
};
const VERDICT_COLORS: Record<string, string> = {
  strong_buy: 'text-emerald-400', buy: 'text-green-400', hold: 'text-amber-400',
  watch: 'text-orange-400', avoid: 'text-red-400',
};

import { useRouter } from 'next/navigation';

export default function DashboardPage() {
  const router = useRouter();
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [stats, setStats]                   = useState<Stats | null>(null);
  const [loading, setLoading]               = useState(true);
  const [search, setSearch]                 = useState('');
  const [filter, setFilter]                 = useState('all');

  useEffect(() => {
    Promise.all([
      api.get('/api/v1/investigations'),
      api.get('/api/v1/analytics/dashboard'),
    ]).then(([invRes, statsRes]) => {
      setInvestigations(invRes.data.investigations || []);
      setStats(statsRes.data.stats);
    }).finally(() => setLoading(false));
  }, []);

  const filtered = investigations.filter(i => {
    const matchSearch = !search ||
      (i.company_name || i.target_url).toLowerCase().includes(search.toLowerCase());
    const matchFilter = filter === 'all' || i.status === filter;
    return matchSearch && matchFilter;
  });

  return (
    <div className="min-h-screen">
      {/* Nav */}
      <nav className="border-b border-slate-800 px-6 py-4 flex items-center justify-between sticky top-0 bg-surface/80 backdrop-blur-sm z-40">
        <Link href="/" prefetch={false} className="flex items-center gap-3 hover:opacity-80 transition-opacity">
          <Brain className="w-5 h-5 text-aegis-400" />
          <span className="font-bold">AEGIS</span>
        </Link>
        <div className="flex items-center gap-3">
          <Link href="/war-room" prefetch={false} className="btn-secondary text-sm">War Room</Link>
          <Link href="/" prefetch={false} className="btn-primary text-sm"><Plus className="w-4 h-4" /> New Investigation</Link>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold mb-1">Intelligence Dashboard</h1>
          <p className="text-slate-500 text-sm">Track all your AEGIS investigations</p>
        </div>

        {/* Stats row */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-8">
            {[
              { label: 'Total',      value: stats.total_investigations, icon: Brain,        color: 'text-aegis-400' },
              { label: 'Completed',  value: stats.completed,            icon: CheckCircle2, color: 'text-emerald-400' },
              { label: 'Running',    value: stats.running,              icon: Clock,        color: 'text-amber-400' },
              { label: 'Avg Vitality',value: `${parseFloat(stats.avg_vitality||'0').toFixed(0)}`, icon: TrendingUp, color: 'text-blue-400' },
              { label: 'Avg Confidence',value: `${(parseFloat(stats.avg_confidence||'0')*100).toFixed(0)}%`, icon: AlertCircle, color: 'text-violet-400' },
              { label: 'Total Cost', value: `$${parseFloat(stats.total_cost||'0').toFixed(2)}`, icon: TrendingUp, color: 'text-green-400' },
            ].map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="card p-4"
              >
                <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
                <div className="text-xs text-slate-500 mt-1">{s.label}</div>
              </motion.div>
            ))}
          </div>
        )}

        {/* Filters */}
        <div className="flex gap-3 mb-6">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search investigations..."
              className="input pl-9 py-2 text-sm"
            />
          </div>
          <div className="flex gap-1 p-1 bg-surface-50 rounded-lg border border-slate-700">
            {['all','running','completed','failed'].map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors capitalize ${
                  filter === f ? 'bg-aegis-600 text-white' : 'text-slate-400 hover:text-slate-200'
                }`}
              >{f}</button>
            ))}
          </div>
        </div>

        {/* Investigations table */}
        {loading ? (
          <div className="card p-12 text-center text-slate-500">Loading...</div>
        ) : filtered.length === 0 ? (
          <div className="card p-12 text-center">
            <Brain className="w-10 h-10 text-slate-700 mx-auto mb-3" />
            <p className="text-slate-500">No investigations found.</p>
            <Link href="/" prefetch={false} className="btn-primary mt-4 inline-flex">Start your first investigation</Link>
          </div>
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800">
                  {['Company / URL','Type','Status','Vitality','Confidence','Started','Duration'].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs text-slate-500 uppercase tracking-wider font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((inv, i) => (
                  <motion.tr
                    key={inv.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.03 }}
                    className="border-b border-slate-800/50 hover:bg-surface-50/50 transition-colors cursor-pointer"
                    onClick={() => router.push(`/investigation?id=${inv.id}`)}
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-200">{inv.company_name || '—'}</div>
                      <div className="text-xs text-slate-500 truncate max-w-[200px]">{inv.target_url}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="badge badge-neutral capitalize">{inv.investigation_type.replace('_',' ')}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`badge ${STATUS_COLORS[inv.status] || 'badge-neutral'}`}>{inv.status}</span>
                    </td>
                    <td className="px-4 py-3">
                      {inv.vitality_score != null ? (
                        <VitalityBar score={inv.vitality_score} />
                      ) : <span className="text-slate-600">—</span>}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-300">
                      {inv.confidence_score != null ? `${(inv.confidence_score * 100).toFixed(0)}%` : '—'}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {new Date(inv.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {inv.duration_ms ? `${(inv.duration_ms / 1000).toFixed(0)}s` : '—'}
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function VitalityBar({ score }: { score: number }) {
  const color = score >= 70 ? 'bg-emerald-500' : score >= 40 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden w-20">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs text-slate-400 font-mono">{score}</span>
    </div>
  );
}
