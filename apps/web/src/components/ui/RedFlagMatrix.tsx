'use client';
import { AlertTriangle, AlertOctagon, Info, Zap } from 'lucide-react';

const SEVERITY_CONFIG = {
  critical: { icon: AlertOctagon, bg: 'bg-red-500/10',    border: 'border-red-500/40',    text: 'text-red-400',    badge: 'bg-red-500/20 text-red-300' },
  high:     { icon: AlertTriangle,bg: 'bg-orange-500/10', border: 'border-orange-500/40', text: 'text-orange-400', badge: 'bg-orange-500/20 text-orange-300' },
  medium:   { icon: Zap,          bg: 'bg-amber-500/10',  border: 'border-amber-500/40',  text: 'text-amber-400',  badge: 'bg-amber-500/20 text-amber-300' },
  low:      { icon: Info,         bg: 'bg-slate-500/10',  border: 'border-slate-500/40',  text: 'text-slate-400',  badge: 'bg-slate-700/50 text-slate-400' },
};

type Flag = { flag: string; severity: string; category: string };

export function RedFlagMatrix({ flags }: { flags: Flag[] }) {
  const sorted = [...flags].sort((a, b) => {
    const order = { critical: 0, high: 1, medium: 2, low: 3 };
    return (order[a.severity as keyof typeof order] ?? 4) - (order[b.severity as keyof typeof order] ?? 4);
  });

  return (
    <div className="card p-5">
      <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 text-red-400" />
        Red Flag Matrix ({flags.length})
      </h3>
      <div className="space-y-2">
        {sorted.map((flag, i) => {
          const cfg = SEVERITY_CONFIG[flag.severity as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.low;
          const Icon = cfg.icon;
          return (
            <div key={i} className={`flex items-start gap-3 p-3 rounded-lg border ${cfg.bg} ${cfg.border}`}>
              <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${cfg.text}`} />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-slate-200">{flag.flag}</div>
                <div className="text-xs text-slate-500 mt-0.5 capitalize">{flag.category}</div>
              </div>
              <span className={`badge shrink-0 capitalize px-2 py-0.5 rounded text-xs font-medium ${cfg.badge}`}>
                {flag.severity}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
