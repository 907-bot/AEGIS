'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Zap, Shield, Brain, ChevronRight, ArrowRight, Globe, BarChart3, Network } from 'lucide-react';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';

const FEATURES = [
  { icon: Brain, label: '7 Specialized Agents', desc: 'Sentry · Financial · Talent · TechStack · Sentiment · Regulatory · Competitive' },
  { icon: Shield, label: 'Adversarial Validation', desc: 'Bull vs Bear vs Skeptic debate ensures balanced, bias-free analysis' },
  { icon: Zap, label: '4-6 Minute Reports', desc: 'Institutional-grade due diligence at 60× the speed of manual research' },
  { icon: Network, label: 'Knowledge Graph', desc: 'Neo4j-powered entity relationships for multi-hop strategic reasoning' },
];

const TYPES = [
  { value: 'competitive',     label: 'Competitive Intel',  desc: 'Map rivals & market position' },
  { value: 'due_diligence',   label: 'Due Diligence',       desc: 'Full investment screening' },
  { value: 'ipo_readiness',   label: 'IPO Readiness',       desc: 'Pre-IPO strategic audit' },
  { value: 'market_analysis', label: 'Market Analysis',     desc: 'Industry landscape mapping' },
];

export default function HomePage() {
  const router = useRouter();
  const [url, setUrl]       = useState('');
  const [type, setType]     = useState('competitive');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    setLoading(true);
    try {
      const res = await api.post('/api/v1/investigations', { url: url.trim(), type });
      toast.success('Investigation launched! Deploying agents...', { icon: '🚀' });
      router.push(`/investigation?id=${res.data.investigationId}`);
    } catch (err: any) {
      toast.error(err.response?.data?.error || 'Failed to start investigation');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid-dots flex flex-col">
      {/* Nav */}
      <nav className="border-b border-slate-800/60 px-6 py-4 flex items-center justify-between backdrop-blur-sm sticky top-0 z-50 bg-surface/80">
        <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
          <div className="w-8 h-8 bg-aegis-600 rounded-lg flex items-center justify-center">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <span className="font-bold text-lg tracking-tight">AEGIS</span>
          <span className="badge badge-info">v1.0</span>
        </Link>
        <div className="flex items-center gap-3">
          <Link href="/dashboard" className="btn-ghost text-sm">Dashboard</Link>
          <Link href="/war-room" className="btn-secondary text-sm">War Room</Link>
        </div>
      </nav>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-20">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center max-w-4xl w-full"
        >
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-aegis-500/10 border border-aegis-500/30 text-aegis-400 text-sm font-medium mb-8">
            <Zap className="w-4 h-4 animate-pulse" />
            Autonomous Multi-Agent Intelligence Platform
          </div>

          {/* Headline */}
          <h1 className="text-5xl md:text-7xl font-bold leading-tight mb-6">
            Drop a URL.<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-aegis-400 to-indigo-400">
              Get Institutional Intel.
            </span>
          </h1>
          <p className="text-xl text-slate-400 mb-12 max-w-2xl mx-auto">
            7 AI agents autonomously investigate any company. Adversarial Bull/Bear/Skeptic
            debate. Strategic report in under 6 minutes. At 1/100th the cost of a human analyst.
          </p>

          {/* Investigation Form */}
          <form onSubmit={handleSubmit} className="card p-6 max-w-2xl mx-auto mb-6">
            <div className="flex gap-3 mb-4">
              <div className="relative flex-1">
                <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                <input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://any-company.com"
                  className="input pl-10"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={loading || !url}
                className="btn-primary px-6 whitespace-nowrap"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Launching...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <Search className="w-4 h-4" /> Investigate
                  </span>
                )}
              </button>
            </div>

            {/* Investigation Type Selector */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => setType(t.value)}
                  className={`p-2.5 rounded-lg border text-left transition-all text-sm ${
                    type === t.value
                      ? 'border-aegis-500 bg-aegis-500/10 text-aegis-300'
                      : 'border-slate-700 hover:border-slate-600 text-slate-400'
                  }`}
                >
                  <div className="font-medium">{t.label}</div>
                  <div className="text-xs text-slate-500 mt-0.5">{t.desc}</div>
                </button>
              ))}
            </div>
          </form>

          {/* Quick examples */}
          <div className="flex flex-wrap gap-2 justify-center mb-16">
            {['stripe.com', 'razorpay.com', 'zepto.com', 'groww.in'].map((ex) => (
              <button
                key={ex}
                onClick={() => setUrl(`https://${ex}`)}
                className="text-xs px-3 py-1.5 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition-colors border border-slate-700 hover:border-slate-600"
              >
                {ex} →
              </button>
            ))}
          </div>

          {/* Features */}
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.label}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 * i + 0.3 }}
                className="card-hover p-5 text-left"
              >
                <div className="w-10 h-10 bg-aegis-600/20 rounded-lg flex items-center justify-center mb-3">
                  <f.icon className="w-5 h-5 text-aegis-400" />
                </div>
                <div className="font-semibold text-sm mb-1">{f.label}</div>
                <div className="text-xs text-slate-500">{f.desc}</div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 px-6 py-4 text-center text-xs text-slate-600">
        AEGIS v1.0 — Autonomous Multi-Agent Strategic Intelligence Platform • Built with Node.js · Python · Go · Next.js
      </footer>
    </div>
  );
}
