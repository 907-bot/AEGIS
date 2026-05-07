// ── ScoreRing ─────────────────────────────────────────────────────────────────
'use client';
export function ScoreRing({
  score, label, color, inverted = false,
}: { score: number; label: string; color: string; inverted?: boolean }) {
  const pct       = Math.min(100, Math.max(0, score));
  const effective = inverted ? 100 - pct : pct;
  const r         = 28;
  const circ      = 2 * Math.PI * r;
  const offset    = circ * (1 - effective / 100);

  const colorMap: Record<string, { stroke: string; text: string; glow: string }> = {
    cyan:    { stroke: '#22d3ee', text: 'text-cyan-400',    glow: 'shadow-cyan-500/30' },
    indigo:  { stroke: '#818cf8', text: 'text-indigo-400',  glow: 'shadow-indigo-500/30' },
    emerald: { stroke: '#34d399', text: 'text-emerald-400', glow: 'shadow-emerald-500/30' },
    red:     { stroke: effective < 40 ? '#34d399' : effective < 70 ? '#fbbf24' : '#f87171',
               text:   effective < 40 ? 'text-emerald-400' : effective < 70 ? 'text-amber-400' : 'text-red-400',
               glow:   'shadow-red-500/30' },
  };
  const c = colorMap[color] || colorMap.cyan;

  return (
    <div className={`card p-5 flex flex-col items-center shadow-lg ${c.glow}`}>
      <svg width="72" height="72" className="-rotate-90">
        <circle cx="36" cy="36" r={r} fill="none" stroke="#1e293b" strokeWidth="6" />
        <circle
          cx="36" cy="36" r={r} fill="none"
          stroke={c.stroke} strokeWidth="6"
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 1s ease-in-out' }}
        />
      </svg>
      <div className={`text-2xl font-bold -mt-2 ${c.text}`}>{pct}</div>
      <div className="text-xs text-slate-500 mt-1">{label}</div>
    </div>
  );
}
