import React, { useState, useEffect, useMemo } from 'react';
import {
  GitFork,
  PlayCircle,
  FileText,
  Search,
  ChevronRight,
  Layers,
  ArrowRight,
  Loader2,
  Copy,
  Check,
  ExternalLink,
  ShieldCheck,
  Sparkles,
  Server,
  Database,
  Cpu,
  Code2,
} from 'lucide-react';
import { api } from '../../api/client';
import type { FeatureFlow, FlowStep } from '../../types';

interface FlowTracerProps {
  activeRepoId?: string;
  onSelectFile?: (filePath: string) => void;
}

export const FlowTracer: React.FC<FlowTracerProps> = ({ activeRepoId, onSelectFile }) => {
  const [flows, setFlows] = useState<any[]>([]);
  const [selectedFlowId, setSelectedFlowId] = useState<string>('');
  const [activeTrace, setActiveTrace] = useState<FeatureFlow | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [diagramMode, setDiagramMode] = useState<'sequence' | 'flowchart'>('sequence');
  const [copiedDiagram, setCopiedDiagram] = useState(false);

  // Load available flows
  useEffect(() => {
    let isCurrent = true;
    api
      .getFlows(activeRepoId)
      .then((res) => {
        if (!isCurrent) return;
        const list = res.flows || [];
        setFlows(list);
        if (list.length > 0) {
          const first = list[0];
          setSelectedFlowId(first.id || first.entry_id || '');
        }
      })
      .catch((err) => console.error('Failed to discover flows:', err));

    return () => {
      isCurrent = false;
    };
  }, [activeRepoId]);

  // Load trace details for selected flow
  useEffect(() => {
    if (!selectedFlowId) return;
    let isCurrent = true;
    setIsLoading(true);

    api
      .traceFlow(selectedFlowId, undefined, activeRepoId)
      .then((data) => {
        if (!isCurrent) return;
        setActiveTrace(data);
      })
      .catch((err) => console.error('Failed to trace flow:', err))
      .finally(() => {
        if (isCurrent) setIsLoading(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [selectedFlowId, activeRepoId]);

  // Categories list
  const categories = useMemo(() => {
    const set = new Set<string>();
    flows.forEach((f) => {
      if (f.category) set.add(f.category);
    });
    return ['All', ...Array.from(set)];
  }, [flows]);

  // Filtered flows
  const filteredFlows = useMemo(() => {
    return flows.filter((f) => {
      const matchCat = selectedCategory === 'All' || f.category === selectedCategory;
      const q = searchQuery.toLowerCase().trim();
      const matchSearch =
        !q ||
        (f.name || '').toLowerCase().includes(q) ||
        (f.file || '').toLowerCase().includes(q) ||
        (f.description || '').toLowerCase().includes(q);
      return matchCat && matchSearch;
    });
  }, [flows, selectedCategory, searchQuery]);

  const handleCopyDiagram = (text: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedDiagram(true);
    setTimeout(() => setCopiedDiagram(false), 2000);
  };

  const getMethodBadge = (name: string, explicitMethod?: string) => {
    let method = explicitMethod || '';
    if (!method && name) {
      const parts = name.split(' ');
      if (['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].includes(parts[0].toUpperCase())) {
        method = parts[0].toUpperCase();
      }
    }
    if (!method) method = 'FLOW';

    let color = 'bg-slate-700/50 text-slate-300 border-slate-600';
    if (method === 'GET') color = 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30';
    else if (method === 'POST') color = 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
    else if (method === 'DELETE') color = 'bg-rose-500/15 text-rose-300 border-rose-500/30';
    else if (['PUT', 'PATCH'].includes(method)) color = 'bg-amber-500/15 text-amber-300 border-amber-500/30';

    return (
      <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-md border ${color}`}>
        {method}
      </span>
    );
  };

  const getStepLayerBadge = (step: FlowStep) => {
    const rel = (step.relationship_type || '').toUpperCase();
    const type = (step.type || '').toUpperCase();
    const path = (step.path || step.file || '').toLowerCase();
    const label = (step.label || step.symbol || '').toLowerCase();

    if (rel === 'ENTRY_POINT' || type === 'API') {
      return (
        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 flex items-center space-x-1">
          <Server className="w-3 h-3" />
          <span>API ENTRY</span>
        </span>
      );
    }
    if (rel === 'MIDDLEWARE' || path.includes('middleware') || ['protect', 'limiter', 'validate'].some((w) => label.includes(w))) {
      return (
        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-purple-500/15 text-purple-300 border border-purple-500/30 flex items-center space-x-1">
          <ShieldCheck className="w-3 h-3" />
          <span>MIDDLEWARE</span>
        </span>
      );
    }
    if (rel === 'HANDLES' || path.includes('controller')) {
      return (
        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 flex items-center space-x-1">
          <Code2 className="w-3 h-3" />
          <span>CONTROLLER</span>
        </span>
      );
    }
    if (rel === 'DISPATCHES' || path.includes('service')) {
      return (
        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center space-x-1">
          <Cpu className="w-3 h-3" />
          <span>SERVICE</span>
        </span>
      );
    }
    if (rel === 'QUERIES' || path.includes('model') || path.includes('schema') || path.includes('db')) {
      return (
        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 flex items-center space-x-1">
          <Database className="w-3 h-3" />
          <span>DATA MODEL</span>
        </span>
      );
    }
    return (
      <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-slate-700/50 text-slate-300 border border-slate-600 flex items-center space-x-1">
        <Layers className="w-3 h-3" />
        <span>{step.type || step.role || 'HANDLER'}</span>
      </span>
    );
  };

  const involvedFiles = activeTrace?.involved_files || activeTrace?.files || [];
  const diagramCode =
    diagramMode === 'sequence'
      ? activeTrace?.mermaid_sequence || activeTrace?.mermaid || ''
      : activeTrace?.mermaid_flowchart || activeTrace?.mermaid_sequence || '';

  return (
    <div className="space-y-6 max-w-7xl mx-auto p-6">
      {/* Header Banner */}
      <div className="glass-panel p-6 rounded-2xl border border-white/10 relative overflow-hidden">
        <div className="absolute -right-20 -top-20 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl pointer-events-none"></div>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 rounded-2xl bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-300 shadow-lg shadow-purple-500/10">
              <GitFork className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-[10px] font-bold tracking-widest uppercase px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-300 border border-purple-500/30">
                  Execution Path Analyzer
                </span>
                <span className="text-xs text-slate-400">Call Graph Tracing</span>
              </div>
              <h2 className="text-2xl font-bold font-futuristic-gradient tracking-tight mt-1">
                Feature Flow &amp; Execution Path Tracer
              </h2>
              <p className="text-xs text-slate-300 mt-1 max-w-2xl leading-relaxed">
                Trace end-to-end execution paths from public HTTP API routes down through authentication
                middleware, controller handlers, domain services, database models, and response formatters.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2 self-start md:self-auto">
            <span className="text-xs font-mono px-3.5 py-1.5 rounded-xl bg-purple-500/15 text-purple-200 border border-purple-500/30 font-bold shadow-sm">
              {flows.length} Identified Flows
            </span>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="glass-panel p-4 rounded-2xl border border-white/10 space-y-3">
        <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
          {/* Search Box */}
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search flows (e.g. login, dashboard, analyze, sessions)..."
              className="w-full bg-slate-900/90 border border-white/10 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-100 placeholder-slate-400 focus:outline-none focus:border-purple-500/60 focus:ring-1 focus:ring-purple-500/40"
            />
          </div>

          {/* Flow Counter */}
          <div className="text-xs text-slate-400 font-mono">
            Showing <span className="text-purple-300 font-bold">{filteredFlows.length}</span> of {flows.length} flows
          </div>
        </div>

        {/* Category Filter Chips */}
        {categories.length > 1 && (
          <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 pt-1">
            {categories.map((cat) => {
              const isSelected = selectedCategory === cat;
              return (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                    isSelected
                      ? 'bg-purple-500/25 border border-purple-500/50 text-purple-200 shadow-sm'
                      : 'bg-white/5 hover:bg-white/10 text-slate-400 hover:text-slate-200 border border-white/5'
                  }`}
                >
                  {cat}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Horizontal Flow Selector Cards */}
      <div className="flex items-center space-x-3 overflow-x-auto pb-2 pt-1 scrollbar-thin">
        {filteredFlows.map((flow) => {
          const id = flow.id || flow.entry_id;
          const isActive = id === selectedFlowId;
          return (
            <button
              key={id}
              onClick={() => setSelectedFlowId(id)}
              className={`p-3 rounded-xl border text-left whitespace-nowrap transition-all flex items-center space-x-3 flex-shrink-0 ${
                isActive
                  ? 'bg-purple-500/20 border-purple-500/50 text-white shadow-lg shadow-purple-500/10 ring-1 ring-purple-500/30'
                  : 'glass-card border-white/5 text-slate-300 hover:border-purple-500/30 hover:text-white'
              }`}
            >
              {getMethodBadge(flow.name || id, flow.method)}
              <div className="flex flex-col truncate">
                <span className="text-xs font-mono font-bold truncate text-white">{flow.name || id}</span>
                {flow.category && (
                  <span className="text-[10px] text-slate-400 truncate">{flow.category}</span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Main Flow Content */}
      {isLoading ? (
        <div className="glass-panel p-16 rounded-2xl border border-white/10 flex flex-col items-center justify-center text-slate-400 space-y-3">
          <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
          <span className="text-sm font-medium">Tracing end-to-end execution sequence...</span>
        </div>
      ) : activeTrace ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Step Timeline (2 cols) */}
          <div className="lg:col-span-2 glass-panel p-6 rounded-2xl border border-white/10 space-y-5">
            {/* Flow Title and Metadata */}
            <div className="border-b border-white/5 pb-4 space-y-2">
              <div className="flex items-center space-x-2">
                <span className="text-[10px] font-mono uppercase font-bold px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                  {activeTrace.category || 'API FLOW'}
                </span>
                <span className="text-xs text-slate-400">
                  {(activeTrace.steps || []).length} Sequential Execution Steps
                </span>
              </div>
              <h3 className="text-xl font-bold font-futuristic-gradient">
                {activeTrace.name}
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                {activeTrace.description ||
                  'Sequential call path discovered from entry point through middlewares, handlers, and downstream data models.'}
              </p>
            </div>

            {/* Step-by-Step Sequence */}
            <div className="space-y-4 pt-1">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                  Step-by-Step Execution Sequence
                </h4>
                <span className="text-[10px] font-mono text-slate-400">
                  Top-down invocation order
                </span>
              </div>

              <div className="relative pl-7 space-y-5 before:content-[''] before:absolute before:left-3 before:top-3 before:bottom-3 before:w-0.5 before:bg-gradient-to-b before:from-amber-400 before:via-purple-500 before:to-emerald-400">
                {(activeTrace.steps || []).map((step, idx) => {
                  const stepNum = step.step_number ?? step.order ?? idx + 1;
                  const stepLabel = step.label ?? step.symbol ?? 'Step';
                  const stepDesc = step.description ?? step.action ?? 'Execution step';
                  const stepPath = step.path ?? step.file ?? '';
                  const relType = step.relationship_type || (idx === 0 ? 'ENTRY_POINT' : 'CALLS');

                  return (
                    <div key={idx} className="relative group">
                      {/* Timeline Bullet */}
                      <div className="absolute -left-[32px] top-3.5 w-4 h-4 rounded-full bg-[#0c101d] border-2 border-purple-400 shadow-md group-hover:border-cyan-400 group-hover:scale-110 transition-all flex items-center justify-center">
                        <span className="w-1.5 h-1.5 rounded-full bg-purple-400 group-hover:bg-cyan-400"></span>
                      </div>

                      {/* Step Card */}
                      <div className="glass-card p-4 rounded-xl border border-white/5 space-y-2.5 hover:border-purple-500/40 hover:bg-[#131b31]/80 transition-all shadow-md">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center space-x-2">
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/20 text-purple-200 border border-purple-500/30 font-bold">
                              STEP {stepNum}
                            </span>
                            <span className="text-sm font-bold text-white font-mono tracking-tight">
                              {stepLabel}
                            </span>
                          </div>

                          <div className="flex items-center space-x-1.5">
                            {getStepLayerBadge(step)}
                            {relType && (
                              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/5 text-slate-400 border border-white/5 uppercase">
                                {relType}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Step Description */}
                        <p className="text-xs text-slate-200 leading-relaxed font-normal">
                          {stepDesc}
                        </p>

                        {/* File link with line */}
                        {stepPath && (
                          <div
                            onClick={() => onSelectFile && onSelectFile(stepPath)}
                            className="inline-flex items-center space-x-1.5 text-[11px] font-mono text-cyan-400/90 hover:text-cyan-200 cursor-pointer pt-1 hover:underline transition-colors"
                            title="Click to view file in File Explorer"
                          >
                            <FileText className="w-3.5 h-3.5 flex-shrink-0" />
                            <span className="truncate">{stepPath}</span>
                            {step.line && <span className="text-cyan-500 font-bold">:{step.line}</span>}
                            <ExternalLink className="w-3 h-3 flex-shrink-0 text-slate-500 ml-1" />
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Right Column: Files & Diagram Preview */}
          <div className="space-y-6">
            {/* Involved Source Files */}
            <div className="glass-panel p-5 rounded-2xl border border-white/10 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center space-x-1.5">
                  <FileText className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Involved Source Files ({involvedFiles.length})</span>
                </h4>
              </div>

              {involvedFiles.length === 0 ? (
                <div className="p-4 text-xs text-slate-400 text-center">
                  No source files associated with this flow.
                </div>
              ) : (
                <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1 scrollbar-thin">
                  {involvedFiles.map((file, idx) => {
                    const parts = file.split('/');
                    const fileName = parts.pop() || file;
                    const dir = parts.join('/');
                    const ext = fileName.split('.').pop()?.toUpperCase() || 'FILE';

                    let extColor = 'bg-slate-800 text-slate-400';
                    if (['JS', 'JSX'].includes(ext)) extColor = 'bg-amber-500/15 text-amber-300 border-amber-500/20';
                    else if (['TS', 'TSX'].includes(ext)) extColor = 'bg-blue-500/15 text-blue-300 border-blue-500/20';
                    else if (['PY'].includes(ext)) extColor = 'bg-emerald-500/15 text-emerald-300 border-emerald-500/20';

                    return (
                      <div
                        key={idx}
                        onClick={() => onSelectFile && onSelectFile(file)}
                        className="p-2 rounded-xl bg-slate-900/60 border border-white/5 hover:border-cyan-500/40 hover:bg-slate-900 cursor-pointer transition-all flex items-center justify-between group"
                      >
                        <div className="truncate min-w-0 mr-2">
                          <div className="text-xs font-mono font-semibold text-slate-200 group-hover:text-cyan-300 truncate">
                            {fileName}
                          </div>
                          {dir && (
                            <div className="text-[10px] font-mono text-slate-400 truncate">
                              {dir}/
                            </div>
                          )}
                        </div>
                        <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${extColor} flex-shrink-0 font-bold`}>
                          {ext}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Architecture Sequence / Flowchart Diagram */}
            {diagramCode && (
              <div className="glass-panel p-5 rounded-2xl border border-white/10 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => setDiagramMode('sequence')}
                      className={`text-[10px] font-mono uppercase font-bold px-2 py-1 rounded-lg transition-all ${
                        diagramMode === 'sequence'
                          ? 'bg-purple-500/20 text-purple-200 border border-purple-500/40'
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      Sequence
                    </button>
                    <button
                      onClick={() => setDiagramMode('flowchart')}
                      className={`text-[10px] font-mono uppercase font-bold px-2 py-1 rounded-lg transition-all ${
                        diagramMode === 'flowchart'
                          ? 'bg-purple-500/20 text-purple-200 border border-purple-500/40'
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      Flowchart
                    </button>
                  </div>

                  <button
                    onClick={() => handleCopyDiagram(diagramCode)}
                    className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white border border-white/5 text-xs flex items-center space-x-1"
                    title="Copy diagram code"
                  >
                    {copiedDiagram ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-[10px] text-emerald-300">Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        <span className="text-[10px]">Copy</span>
                      </>
                    )}
                  </button>
                </div>

                <pre className="p-3.5 rounded-xl bg-slate-950/80 border border-white/5 text-[11px] font-mono text-cyan-300/90 overflow-x-auto max-h-72 leading-relaxed">
                  {diagramCode}
                </pre>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="glass-panel p-16 rounded-2xl border border-white/10 text-center space-y-3">
          <GitFork className="w-8 h-8 text-slate-500 mx-auto" />
          <h3 className="text-base font-bold text-white">No Feature Flow Selected</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            Select an endpoint or feature flow from the list above to trace its complete execution path.
          </p>
        </div>
      )}
    </div>
  );
};
