'use client';
import { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
         RadarChart, PolarGrid, PolarAngleAxis, Radar } from 'recharts';
import { api } from '@/lib/api';
import toast from 'react-hot-toast';
import { Play, Loader2 } from 'lucide-react';

// ── Scenario Simulator ────────────────────────────────────────────────────────
export function ScenarioSimulator({
  investigationId, baseScores,
}: { investigationId: string; baseScores: { vitality: number; moat: number; risk: number } }) {
  const [params, setParams] = useState({
    priceChange: 0, regulatoryImpact: 5, competitorEntry: false, fundingRound: 'none',
  });
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    try {
      const res = await api.post('/api/v1/analytics/simulate', { investigationId, params });
      setResult(res.data);
    } catch { toast.error('Simulation failed'); }
    finally { setLoading(false); }
  };

  const chartData = result ? [
    { name: 'Bear (P10)', score: result.scenarios.bear.score, fill: '#f87171' },
    { name: 'Base (P50)', score: result.scenarios.base.score, fill: '#fbbf24' },
    { name: 'Bull (P90)', score: result.scenarios.bull.score, fill: '#34d399' },
  ] : [];

  return (
    <div className="space-y-5">
      <div className="card p-5">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">
          What-If Scenario Simulator (Monte Carlo)
        </h3>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <SliderInput
            label={`Price Change: ${params.priceChange > 0 ? '+' : ''}${params.priceChange}%`}
            min={-50} max={50} value={params.priceChange}
            onChange={v => setParams(p => ({ ...p, priceChange: v }))}
          />
          <SliderInput
            label={`Regulatory Impact: ${params.regulatoryImpact}/10`}
            min={0} max={10} value={params.regulatoryImpact}
            onChange={v => setParams(p => ({ ...p, regulatoryImpact: v }))}
          />
        </div>
        <div className="flex gap-4 mb-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={params.competitorEntry}
              onChange={e => setParams(p => ({ ...p, competitorEntry: e.target.checked }))}
              className="w-4 h-4 rounded accent-aegis-500"
            />
            <span className="text-sm text-slate-300">New Competitor Entry</span>
          </label>
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-400">Funding Round:</span>
            <select
              value={params.fundingRound}
              onChange={e => setParams(p => ({ ...p, fundingRound: e.target.value }))}
              className="input py-1 text-sm w-32"
            >
              {['none','seed','series_a','series_b','ipo'].map(v => (
                <option key={v} value={v}>{v.replace('_',' ').toUpperCase()}</option>
              ))}
            </select>
          </div>
        </div>
        <button onClick={run} disabled={loading} className="btn-primary w-full">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          {loading ? 'Running 1000 simulations...' : 'Run Monte Carlo Simulation'}
        </button>
      </div>

      {result && (
        <div className="card p-5">
          <div className="grid grid-cols-3 gap-3 mb-5">
            {[
              { key: 'bear', label: 'Bear Case', color: 'text-red-400',     bg: 'bg-red-500/10' },
              { key: 'base', label: 'Base Case', color: 'text-amber-400',   bg: 'bg-amber-500/10' },
              { key: 'bull', label: 'Bull Case', color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
            ].map(s => (
              <div key={s.key} className={`rounded-xl p-4 ${s.bg} border border-slate-700 text-center`}>
                <div className={`text-3xl font-bold ${s.color}`}>{result.scenarios[s.key].score}</div>
                <div className="text-xs text-slate-500 mt-1">{s.label}</div>
                <div className="text-xs text-slate-400 mt-1">{result.scenarios[s.key].label.split('(')[1]?.replace(')','')}</div>
              </div>
            ))}
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 11 }} />
              <YAxis domain={[0,100]} tick={{ fill: '#64748b', fontSize: 11 }} />
              <Tooltip contentStyle={{ background:'#1e293b',border:'1px solid #334155',borderRadius:'8px' }} />
              <Bar dataKey="score" radius={[6,6,0,0]}>
                {chartData.map((entry, i) => (
                  <rect key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function SliderInput({ label, min, max, value, onChange }: {
  label: string; min: number; max: number; value: number; onChange: (v: number) => void;
}) {
  return (
    <div>
      <label className="text-xs text-slate-400 mb-1.5 block">{label}</label>
      <input
        type="range" min={min} max={max} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full accent-aegis-500"
      />
    </div>
  );
}

