'use client';
import { motion } from 'framer-motion';
import { CheckCircle2, XCircle, Clock, Loader2 } from 'lucide-react';

type AgentEvent = {
  agentType: string; status: string; currentAction: string;
  confidence: number; evidenceCount: number; latencyMs: number;
};

export function AgentCard({
  agentKey, meta, event,
}: {
  agentKey: string;
  meta: { icon: any; color: string; label: string };
  event: AgentEvent | null;
}) {
  const Icon   = meta.icon;
  const status = event?.status || 'pending';

  const statusIcon = {
    completed:   <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
    failed:      <XCircle className="w-4 h-4 text-red-400" />,
    timeout:     <XCircle className="w-4 h-4 text-amber-400" />,
    in_progress: <Loader2 className="w-4 h-4 text-aegis-400 animate-spin" />,
    started:     <Loader2 className="w-4 h-4 text-aegis-400 animate-spin" />,
    pending:     <Clock className="w-4 h-4 text-slate-600" />,
  }[status] || <Clock className="w-4 h-4 text-slate-600" />;

  const borderColor = {
    completed:   'border-emerald-500/30',
    failed:      'border-red-500/30',
    in_progress: 'border-aegis-500/50',
    started:     'border-aegis-500/50',
    pending:     'border-slate-700/50',
  }[status] || 'border-slate-700/50';

  return (
    <motion.div
      layout
      className={`card px-4 py-3 border transition-all duration-300 ${borderColor} ${
        ['in_progress','started'].includes(status) ? 'animate-glow' : ''
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center`}>
            <Icon className={`w-4 h-4 ${meta.color}`} />
          </div>
          <div>
            <div className="text-sm font-medium">{meta.label}</div>
            {event?.currentAction && (
              <div className="text-xs text-slate-500 truncate max-w-[160px]">
                {event.currentAction}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {event?.confidence > 0 && (
            <span className="text-xs text-slate-500 font-mono">
              {(event.confidence * 100).toFixed(0)}%
            </span>
          )}
          {statusIcon}
        </div>
      </div>

      {/* Progress bar for in-progress */}
      {['in_progress','started'].includes(status) && (
        <div className="mt-2 h-0.5 bg-slate-800 rounded-full overflow-hidden">
          <div className="h-full bg-aegis-500 rounded-full animate-pulse w-3/4" />
        </div>
      )}

      {/* Evidence count on completion */}
      {status === 'completed' && event?.evidenceCount > 0 && (
        <div className="mt-1.5 flex gap-3 text-xs text-slate-600">
          <span>{event.evidenceCount} signals</span>
          {event.latencyMs > 0 && <span>{(event.latencyMs/1000).toFixed(1)}s</span>}
        </div>
      )}
    </motion.div>
  );
}
