'use client';
import { useState } from 'react';
import { TrendingUp, TrendingDown, Eye, Layers } from 'lucide-react';

// ── Debate Chamber ────────────────────────────────────────────────────────────
export function DebateChamber({ inv }: { inv: any }) {
  const [activeDebater, setActiveDebater] = useState<'bull'|'bear'|'skeptic'|'synth'>('bull');
  const tabs = [
    { id: 'bull',    label: '🐂 Bull',    icon: TrendingUp,   color: 'text-emerald-400', border: 'border-emerald-500/40' },
    { id: 'bear',    label: '🐻 Bear',    icon: TrendingDown, color: 'text-red-400',     border: 'border-red-500/40' },
    { id: 'skeptic', label: '🔍 Skeptic', icon: Eye,          color: 'text-amber-400',   border: 'border-amber-500/40' },
    { id: 'synth',   label: '⚡ Synthesis',icon: Layers,      color: 'text-aegis-400',   border: 'border-aegis-500/40' },
  ] as const;

  const content: Record<string, string> = {
    bull:    inv.bull_thesis    || 'Bull thesis not available.',
    bear:    inv.bear_thesis    || 'Bear thesis not available.',
    skeptic: inv.skeptic_analysis || 'Skeptic analysis not available.',
    synth:   inv.executive_summary || 'Synthesis not available.',
  };

  const active = tabs.find(t => t.id === activeDebater)!;

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveDebater(t.id)}
            className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium border transition-all ${
              activeDebater === t.id
                ? `${t.border} ${t.color} bg-surface-50`
                : 'border-slate-700 text-slate-500 hover:text-slate-300'
            }`}
          >{t.label}</button>
        ))}
      </div>
      <div className={`card p-6 border-l-4 ${active.border}`}>
        <div className={`text-sm font-semibold ${active.color} mb-3`}>{active.label}</div>
        <div className="text-slate-300 leading-relaxed whitespace-pre-wrap text-sm">
          {content[activeDebater]}
        </div>
      </div>
    </div>
  );
}
