'use client';
import { useEffect, useRef, useState } from 'react';
import { Network, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';

export function KnowledgeGraph({
  data, investigationId,
}: { data: { nodes: any[]; edges: any[] } | null; investigationId: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef        = useRef<any>(null);
  const [loading, setLoading]   = useState(false);
  const [graphData, setGraphData] = useState(data);

  const loadGraph = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/api/v1/investigations/${investigationId}/graph-data`);
      setGraphData(res.data);
    } finally { setLoading(false); }
  };

  useEffect(() => {
    if (!graphData) { loadGraph(); return; }
    if (!containerRef.current) return;

    import('cytoscape').then(({ default: cytoscape }) => {
      if (cyRef.current) cyRef.current.destroy();

      const elements = [
        ...graphData.nodes.map(n => ({
          data: {
            id: n.id,
            label: n.label || n.id,
            type: n.type || 'Entity',
          },
        })),
        ...graphData.edges.map((e, i) => ({
          data: {
            id:     `e${i}`,
            source: e.source,
            target: e.target,
            label:  e.label || '',
            weight: (e.confidence || 0.5) * 10,
          },
        })),
      ];

      if (elements.length === 0) return;

      cyRef.current = cytoscape({
        container: containerRef.current,
        elements,
        style: [
          {
            selector: 'node',
            style: {
              'background-color':  '#0ea5e9',
              'label':             'data(label)',
              'color':             '#f1f5f9',
              'font-size':         '10px',
              'text-valign':       'bottom',
              'text-margin-y':     '4px',
              'border-width':      2,
              'border-color':      '#334155',
              'width':             40,
              'height':            40,
            },
          },
          {
            selector: 'node[type="Company"]',
            style: {
              'background-color': '#6366f1',
              'width': 56, 'height': 56,
            },
          },
          {
            selector: 'node[type="Technology"]',
            style: { 'background-color': '#22d3ee' },
          },
          {
            selector: 'node[type="Person"]',
            style: { 'background-color': '#a78bfa' },
          },
          {
            selector: 'edge',
            style: {
              'width':           'mapData(weight, 0, 10, 1, 5)',
              'line-color':      '#334155',
              'target-arrow-color': '#334155',
              'target-arrow-shape': 'triangle',
              'curve-style':     'bezier',
              'label':           'data(label)',
              'font-size':       '8px',
              'color':           '#64748b',
            },
          },
        ],
        layout: { name: 'cose', animate: true, animationDuration: 800, nodeRepulsion: 8000 },
      });

      // Click to highlight
      cyRef.current.on('tap', 'node', (evt: any) => {
        const node = evt.target;
        cyRef.current.elements().removeClass('highlighted dimmed');
        node.addClass('highlighted');
        node.neighborhood().addClass('highlighted');
        cyRef.current.elements().not(node.neighborhood().add(node)).addClass('dimmed');
      });
      cyRef.current.on('tap', (evt: any) => {
        if (evt.target === cyRef.current) {
          cyRef.current.elements().removeClass('highlighted dimmed');
        }
      });
    });

    return () => { if (cyRef.current) cyRef.current.destroy(); };
  }, [graphData]);

  const hasData = graphData && (graphData.nodes.length > 0 || graphData.edges.length > 0);

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Network className="w-4 h-4 text-aegis-400" />
          <span className="text-sm font-semibold">Knowledge Graph</span>
          {hasData && (
            <span className="badge badge-info">
              {graphData.nodes.length}N · {graphData.edges.length}E
            </span>
          )}
        </div>
        <button onClick={loadGraph} className="btn-ghost p-1.5" disabled={loading}>
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {!hasData ? (
        <div className="h-72 flex flex-col items-center justify-center text-slate-600">
          <Network className="w-10 h-10 mb-3 opacity-30" />
          <p className="text-sm">Graph data not available yet</p>
          <button onClick={loadGraph} className="btn-secondary mt-3 text-xs">
            Load Graph
          </button>
        </div>
      ) : (
        <div ref={containerRef} className="h-[500px] w-full bg-surface" />
      )}

      {/* Legend */}
      {hasData && (
        <div className="flex gap-4 px-5 py-3 border-t border-slate-800 text-xs text-slate-500">
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-indigo-500" />Company</span>
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-cyan-400" />Technology</span>
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-violet-400" />Person</span>
        </div>
      )}
    </div>
  );
}
