'use client';
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer } from 'recharts';

export function MoatRadar({ moat }: { moat: any }) {
  if (!moat) return null;

  const moatTypeScores: Record<string, number> = {
    network_effects:   moat.primary_moat === 'network_effects'  ? 90 : 30,
    switching_costs:   moat.primary_moat === 'switching_costs'  ? 85 : 25,
    cost_advantage:    moat.primary_moat === 'cost_advantage'   ? 80 : 30,
    brand:             moat.primary_moat === 'brand'            ? 75 : 20,
    ip:                moat.primary_moat === 'ip'               ? 70 : 20,
    regulatory:        moat.regulatory_approval_needed ? 60 : 15,
  };

  const data = Object.entries(moatTypeScores).map(([k, v]) => ({
    subject: k.replace('_', ' '),
    score: v,
  }));

  return (
    <div className="card p-5">
      <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2">Moat Analysis</h3>
      <div className="flex items-center gap-2 mb-3">
        <span className="badge badge-info capitalize">{moat.primary_moat?.replace('_',' ') || 'None'}</span>
        <span className={`badge ${moat.strength === 'wide' ? 'badge-success' : moat.strength === 'narrow' ? 'badge-warning' : 'badge-danger'}`}>
          {moat.strength || 'none'}
        </span>
        {moat.durability_years && <span className="text-xs text-slate-500">{moat.durability_years}yr durability</span>}
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <RadarChart data={data}>
          <PolarGrid stroke="#1e293b" />
          <PolarAngleAxis dataKey="subject" tick={{ fill: '#64748b', fontSize: 10 }} />
          <Radar dataKey="score" stroke="#0ea5e9" fill="#0ea5e9" fillOpacity={0.2} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

