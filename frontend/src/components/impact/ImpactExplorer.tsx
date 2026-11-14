import React, { useState, useEffect, useMemo } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  FileCode,
  Link2,
  Server,
  FlaskConical,
  Sparkles,
  ArrowRight,
  ExternalLink,
} from 'lucide-react';
import { api } from '../../api/client';
import type { AnalysisData, GraphNode, ImpactResponse } from '../../types';

interface ImpactExplorerProps {
  analysis: AnalysisData;
  activeRepoId?: string;
  initialNodeId?: string;
  onAskAiBlastRadius?: (targetLabel: string, risk: string) => void;
  onNavigateToGraph?: () => void;
  onOpenFile?: (filePath: string) => void;
}

export const ImpactExplorer: React.FC<ImpactExplorerProps> = ({
  analysis,
  activeRepoId,
  initialNodeId,
  onAskAiBlastRadius,
  onNavigateToGraph,
  onOpenFile,
}) => {
  const nodes = analysis.nodes || [];

  // Filter candidate symbols case-insensitively and sort so high-impact components appear first
  const candidateNodes = useMemo(() => {
    const list = nodes.filter((n) => {
      const t = (n.type || '').toLowerCase();
      return (
        t === 'function' ||
        t === 'method' ||
        t === 'class' ||
        t === 'endpoint' ||
        t === 'api' ||
        t === 'file'
      );
    });

    const impactMap = analysis.impact_index || {};
    const riskWeight = (id: string) => {
      const r = impactMap[id]?.risk;
      if (r === 'High') return 3;
      if (r === 'Medium') return 2;
      return 1;
    };

    return list.sort((a, b) => {
      const diff = riskWeight(b.id) - riskWeight(a.id);
      if (diff !== 0) return diff;
      return a.label.localeCompare(b.label);
    });
  }, [nodes, analysis.impact_index]);

  const [selectedNodeId, setSelectedNodeId] = useState<string>(
    initialNodeId || candidateNodes[0]?.id || ''
  );
  const [targetSearch, setTargetSearch] = useState('');
  const [filterCategory, setFilterCategory] = useState<'all' | 'high' | 'medium' | 'apis' | 'functions'>('all');
  const [impactData, setImpactData] = useState<ImpactResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Sync if initialNodeId changes
  useEffect(() => {
    if (initialNodeId && initialNodeId !== selectedNodeId) {
      setSelectedNodeId(initialNodeId);
    }
  }, [initialNodeId]);

  // Fetch impact whenever selected node changes
  useEffect(() => {
    if (!selectedNodeId) return;
    let isCurrent = true;
    setIsLoading(true);

    api
      .getImpact(selectedNodeId, activeRepoId)
      .then((data) => {
        if (!isCurrent) return;
        setImpactData(data);
      })
      .catch((err) => {
        console.error('Failed to load impact:', err);
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [selectedNodeId, activeRepoId]);

  const filteredCandidates = useMemo(() => {
    let list = candidateNodes;
    const impactMap = analysis.impact_index || {};

    if (filterCategory === 'high') {
      list = list.filter((n) => impactMap[n.id]?.risk === 'High');
    } else if (filterCategory === 'medium') {
      list = list.filter((n) => impactMap[n.id]?.risk === 'Medium');
    } else if (filterCategory === 'apis') {
      list = list.filter((n) => {
        const t = (n.type || '').toLowerCase();
        return t === 'api' || t === 'endpoint';
      });
    } else if (filterCategory === 'functions') {
      list = list.filter((n) => ['function', 'method', 'class'].includes((n.type || '').toLowerCase()));
    }

    if (targetSearch.trim()) {
      const q = targetSearch.toLowerCase();
      list = list.filter(
        (n) => n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q)
      );
    }
    return list;
  }, [candidateNodes, targetSearch, filterCategory, analysis.impact_index]);

  const riskBadgeColor =
    impactData?.risk === 'High'
      ? 'bg-rose-500/15 text-rose-400 border-rose-500/30'
      : impactData?.risk === 'Medium'
      ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
      : 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30';

  const riskProgressColor =
    impactData?.risk === 'High'
      ? 'bg-gradient-to-r from-amber-500 to-rose-500'
      : impactData?.risk === 'Medium'
      ? 'bg-gradient-to-r from-cyan-500 to-amber-500'
      : 'bg-gradient-to-r from-emerald-500 to-cyan-500';

  return (
    <div className="space-y-6 max-w-7xl mx-auto p-6">
      {/* Target Selector & Filter Console */}
      <div className="glass-panel p-5 rounded-2xl border border-white/10 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-tight">
                Change Impact &amp; Blast Radius Explorer
              </h2>
              <p className="text-xs text-slate-400">
                Simulate potential regressions and cascading ripples before committing changes
              </p>
            </div>
          </div>

          {/* Target Select Dropdown */}
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="text"
              placeholder="Search target symbol..."
              value={targetSearch}
              onChange={(e) => setTargetSearch(e.target.value)}
              className="bg-slate-900/80 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 w-44"
            />
            <select
              value={selectedNodeId}
              onChange={(e) => setSelectedNodeId(e.target.value)}
              className="bg-slate-900 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500/50 max-w-xs truncate"
            >
              {filteredCandidates.map((n) => {
                const impactMap = analysis.impact_index || {};
                const r = impactMap[n.id]?.risk;
                const riskPrefix = r ? `[${r.toUpperCase()}] ` : '';
                return (
                  <option key={n.id} value={n.id}>
                    {riskPrefix}[{(n.type || 'SYMBOL').toUpperCase()}] {n.label}
                  </option>
                );
              })}
            </select>
          </div>
        </div>

        {/* Category Filter Pills */}
        <div className="flex items-center space-x-2 pt-2 border-t border-white/5 overflow-x-auto">
          <span className="text-[10px] font-bold text-slate-400 uppercase mr-1">Filter:</span>
          {(['all', 'high', 'medium', 'apis', 'functions'] as const).map((cat) => (
            <button
              key={cat}
              onClick={() => setFilterCategory(cat)}
              className={`px-2.5 py-1 rounded-lg text-xs capitalize font-medium transition-all ${
                filterCategory === cat
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                  : 'bg-white/5 text-slate-400 hover:text-slate-200 hover:bg-white/10'
              }`}
            >
              {cat === 'high' ? 'High Risk' : cat === 'medium' ? 'Medium Risk' : cat}
            </button>
          ))}
          <span className="text-[11px] font-mono text-slate-500 ml-auto">
            {filteredCandidates.length} symbols available
          </span>
        </div>
      </div>

      {/* Target Details Card */}
      {impactData && (
        <div className="glass-panel p-6 rounded-2xl border border-white/10 space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-white/5">
            <div>
              <div className="flex items-center space-x-3">
                <h3 className="text-xl font-bold text-white font-mono">
                  {impactData.target?.label || selectedNodeId}
                </h3>
                <span className="text-[10px] px-2 py-0.5 rounded uppercase font-bold tracking-wider bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 font-mono">
                  {impactData.target?.type || 'Entity'}
                </span>
              </div>

              {impactData.target?.path && (
                <div
                  onClick={() => onOpenFile && onOpenFile(impactData.target.path!)}
                  className="text-xs text-cyan-400/90 hover:text-cyan-300 font-mono mt-1 cursor-pointer flex items-center space-x-1"
                  title="Click to view file in code viewer"
                >
                  <FileCode className="w-3.5 h-3.5" />
                  <span>{impactData.target.path}</span>
                  {impactData.target?.line ? <span>:{impactData.target.line}</span> : null}
                  <ExternalLink className="w-3 h-3 text-cyan-400/60" />
                </div>
              )}
            </div>

            <div className="flex items-center space-x-4">
              {/* Risk Level Badge */}
              <div className="flex flex-col items-end">
                <span
                  className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border ${riskBadgeColor}`}
                >
                  {impactData.risk || 'Low'} Risk
                </span>
                <div className="w-32 bg-slate-800 rounded-full h-1.5 mt-2 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${riskProgressColor}`}
                    style={{ width: `${Math.max(10, impactData.blast_score || 20)}%` }}
                  ></div>
                </div>
                <span className="text-[10px] font-mono text-slate-400 mt-1">
                  Blast Radius: {impactData.blast_score || 0}%
                </span>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-col space-y-2">
                {onNavigateToGraph && (
                  <button
                    onClick={onNavigateToGraph}
                    className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-semibold text-slate-200 transition-all flex items-center space-x-1.5"
                  >
                    <span>View in Graph</span>
                  </button>
                )}
                {onAskAiBlastRadius && (
                  <button
                    onClick={() =>
                      onAskAiBlastRadius(
                        impactData.target?.label || selectedNodeId,
                        impactData.risk
                      )
                    }
                    className="px-3 py-1.5 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-500/30 text-xs font-semibold text-cyan-300 transition-all flex items-center space-x-1.5"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Ask AI Blast Radius</span>
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* 4 Stat Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl glass-card border border-white/5">
              <div className="flex items-center space-x-2 text-cyan-400 mb-1">
                <FileCode className="w-4 h-4" />
                <span className="text-xs font-medium text-slate-400">Downstream Files</span>
              </div>
              <div className="text-xl font-bold text-white font-mono">
                {impactData.affected_files?.length || 0}
              </div>
            </div>

            <div className="p-4 rounded-xl glass-card border border-white/5">
              <div className="flex items-center space-x-2 text-purple-400 mb-1">
                <Link2 className="w-4 h-4" />
                <span className="text-xs font-medium text-slate-400">1-Hop Direct Callers</span>
              </div>
              <div className="text-xl font-bold text-white font-mono">
                {impactData.direct_dependents?.length || 0}
              </div>
            </div>

            <div className="p-4 rounded-xl glass-card border border-white/5">
              <div className="flex items-center space-x-2 text-amber-400 mb-1">
                <Server className="w-4 h-4" />
                <span className="text-xs font-medium text-slate-400">Exposed APIs Impacted</span>
              </div>
              <div className="text-xl font-bold text-white font-mono">
                {impactData.affected_apis?.length || 0}
              </div>
            </div>

            <div className="p-4 rounded-xl glass-card border border-white/5">
              <div className="flex items-center space-x-2 text-emerald-400 mb-1">
                <FlaskConical className="w-4 h-4" />
                <span className="text-xs font-medium text-slate-400">Affected Test Suites</span>
              </div>
              <div className="text-xl font-bold text-white font-mono">
                {impactData.affected_tests?.length || 0}
              </div>
            </div>
          </div>

          {/* Dependent Callers & Guidance Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-2">
            {/* Direct Callers */}
            <div className="glass-card p-4 rounded-xl border border-white/5 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                  Direct Callers (1-Hop)
                </h4>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300">
                  {impactData.direct_dependents?.length || 0}
                </span>
              </div>
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {(impactData.direct_dependents || []).length > 0 ? (
                  impactData.direct_dependents.map((dep, idx) => (
                    <div
                      key={idx}
                      onClick={() => dep.file && onOpenFile && onOpenFile(dep.file)}
                      className="p-2.5 rounded-lg bg-slate-900/60 border border-white/5 hover:border-cyan-500/30 cursor-pointer text-xs space-y-1 transition-all"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-white truncate mr-2">{dep.name}</span>
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-slate-400 font-mono">
                          {dep.relation}
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-400 font-mono truncate">{dep.file}</div>
                    </div>
                  ))
                ) : (
                  <div className="text-xs text-slate-500 py-4 text-center">
                    No direct upstream callers detected.
                  </div>
                )}
              </div>
            </div>

            {/* APIs & Transitive */}
            <div className="glass-card p-4 rounded-xl border border-white/5 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                  APIs &amp; Transitive (2-Hop)
                </h4>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-300">
                  {impactData.transitive_dependents?.length || 0}
                </span>
              </div>
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {(impactData.transitive_dependents || []).length > 0 ? (
                  impactData.transitive_dependents.map((dep, idx) => (
                    <div
                      key={idx}
                      onClick={() => dep.file && onOpenFile && onOpenFile(dep.file)}
                      className="p-2.5 rounded-lg bg-slate-900/60 border border-white/5 hover:border-cyan-500/30 cursor-pointer text-xs space-y-1 transition-all"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-200 truncate mr-2">{dep.name}</span>
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-slate-400 font-mono">
                          {dep.relation}
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-400 font-mono truncate">{dep.file}</div>
                    </div>
                  ))
                ) : (
                  <div className="text-xs text-slate-500 py-4 text-center">
                    No downstream API routes or 2-hop consumers impacted.
                  </div>
                )}
              </div>
            </div>

            {/* Pre-Merge Risk Guidance */}
            <div className="glass-card p-4 rounded-xl border border-white/5 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                  Pre-Merge Risk Guidance
                </h4>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-300">
                  Checklist
                </span>
              </div>
              <div className="space-y-2 text-xs">
                {(impactData.recommendations || []).map((rec, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded-lg bg-slate-900/60 border border-white/5 text-slate-300 flex items-start space-x-2"
                  >
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
                    <span className="leading-snug">{rec}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
