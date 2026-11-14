import React from 'react';
import {
  FileCode2,
  Code,
  Box,
  Layers,
  Sparkles,
  Server,
  FolderGit2,
  ArrowRight,
  ShieldAlert,
  ExternalLink,
} from 'lucide-react';
import type { AnalysisData } from '../../types';
import type { NavTab } from '../layout/Sidebar';

interface OverviewViewProps {
  analysis: AnalysisData;
  onNavigate: (tab: NavTab) => void;
  onOpenFile: (filePath: string) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  analysis,
  onNavigate,
  onOpenFile,
}) => {
  const summary = analysis.summary || {};
  const stats = summary.stats || {};

  // Compute counts from analysis.nodes with fallbacks
  const nodes = analysis.nodes || [];
  const nodeTypeCounts = React.useMemo(() => {
    const counts: Record<string, number> = {};
    for (const n of nodes) {
      const t = n.type || '';
      counts[t] = (counts[t] || 0) + 1;
    }
    return counts;
  }, [nodes]);

  const filesCount = stats.files ?? stats.total_files ?? (analysis.files?.length || nodeTypeCounts['File'] || 0);
  const functionsCount = stats.functions ?? stats.total_functions ?? (nodeTypeCounts['Function'] || 0);
  const classesCount = stats.classes ?? stats.total_classes ?? (nodeTypeCounts['Class'] || 0);
  const apisCount = stats.apis ?? stats.total_apis ?? (analysis.apis?.length || nodeTypeCounts['API'] || 0);

  const statCards = [
    {
      label: 'Source Files',
      value: filesCount,
      icon: FileCode2,
      color: 'from-blue-500/20 to-cyan-500/10 text-cyan-400 border-cyan-500/20',
      action: () => onNavigate('files'),
    },
    {
      label: 'Functions & Methods',
      value: functionsCount,
      icon: Code,
      color: 'from-purple-500/20 to-indigo-500/10 text-purple-400 border-purple-500/20',
      action: () => onNavigate('graph'),
    },
    {
      label: 'Classes & Modules',
      value: classesCount,
      icon: Box,
      color: 'from-emerald-500/20 to-teal-500/10 text-emerald-400 border-emerald-500/20',
      action: () => onNavigate('graph'),
    },
    {
      label: 'HTTP API Endpoints',
      value: apisCount,
      icon: Server,
      color: 'from-amber-500/20 to-orange-500/10 text-amber-400 border-amber-500/20',
      action: () => onNavigate('apis'),
    },
  ];

  const entryPoints =
    summary.entry_points && summary.entry_points.length > 0
      ? summary.entry_points
      : (analysis.files || []).slice(0, 3).map((f) => (typeof f === 'string' ? f : f.path));

  const architectureLayers = summary.architecture_layers || [];

  return (
    <div className="space-y-6 max-w-7xl mx-auto p-6">
      {/* Hero Architecture Card */}
      <div className="glass-panel p-6 rounded-2xl border border-white/10 relative overflow-hidden">
        <div className="absolute -right-20 -top-20 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none"></div>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div className="space-y-2 max-w-3xl">
            <div className="flex items-center space-x-2">
              <span className="text-[10px] font-bold tracking-widest uppercase px-2.5 py-0.5 rounded-full bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                {summary.architecture_style || 'SERVICE ARCHITECTURE'}
              </span>
              <span className="text-xs text-slate-400">Analysis Snapshot</span>
            </div>
            <h2 className="text-2xl font-bold font-futuristic-gradient tracking-tight">
              {summary.headline || `${analysis.repository?.name || 'Codebase'} Architecture Overview`}
            </h2>
            <p className="text-sm text-slate-300 leading-relaxed">
              {summary.purpose ||
                'Comprehensive architectural graph, execution flow paths, and change blast radius analysis.'}
            </p>
          </div>

          <div className="flex flex-wrap gap-2 md:self-end">
            <button
              onClick={() => onNavigate('graph')}
              className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-semibold text-slate-200 flex items-center space-x-2 transition-all"
            >
              <span>Explore Graph</span>
              <ArrowRight className="w-3.5 h-3.5 text-cyan-400" />
            </button>
            <button
              onClick={() => onNavigate('impact')}
              className="px-4 py-2 rounded-xl bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-xs font-semibold text-cyan-300 flex items-center space-x-2 transition-all"
            >
              <span>Blast Radius</span>
              <ArrowRight className="w-3.5 h-3.5 text-cyan-400" />
            </button>
          </div>
        </div>
      </div>

      {/* 4 Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <div
              key={idx}
              onClick={card.action}
              className={`p-5 rounded-2xl glass-card border bg-gradient-to-br ${card.color} flex items-center justify-between cursor-pointer transition-all hover:scale-[1.02]`}
            >
              <div>
                <div className="text-xs font-medium text-slate-400">{card.label}</div>
                <div className="text-2xl font-bold text-white font-mono mt-1">
                  {card.value.toLocaleString()}
                </div>
              </div>
              <div className="p-3 rounded-xl bg-white/5 border border-white/10">
                <Icon className="w-5 h-5" />
              </div>
            </div>
          );
        })}
      </div>

      {/* Primary Entry Points & Architecture Layers Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* CLICKABLE Primary Entry Points */}
        <div className="glass-panel p-5 rounded-2xl border border-white/10 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <FolderGit2 className="w-4 h-4 text-cyan-400" />
              <h3 className="text-sm font-semibold text-white">Primary Entry Points</h3>
            </div>
            <span className="text-[10px] text-slate-400 font-mono">Click to view in code viewer</span>
          </div>

          <div className="space-y-2">
            {entryPoints.map((entry, idx) => (
              <div
                key={idx}
                onClick={() => onOpenFile(entry)}
                className="p-3 rounded-xl bg-slate-900/70 border border-white/5 hover:border-cyan-500/40 hover:bg-cyan-950/20 cursor-pointer flex items-center justify-between transition-all group"
                title={`Open ${entry} in File Explorer`}
              >
                <div className="flex items-center space-x-2.5 truncate mr-2">
                  <FileCode2 className="w-4 h-4 text-cyan-400/80 group-hover:text-cyan-300 flex-shrink-0" />
                  <span className="font-mono text-xs text-slate-200 group-hover:text-cyan-200 truncate font-semibold">
                    {entry}
                  </span>
                </div>
                <div className="flex items-center space-x-2 flex-shrink-0">
                  <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 font-bold">
                    ENTRY
                  </span>
                  <ExternalLink className="w-3.5 h-3.5 text-slate-500 group-hover:text-cyan-400" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Architecture Layers */}
        <div className="glass-panel p-5 rounded-2xl border border-white/10 space-y-4">
          <div className="flex items-center space-x-2">
            <Layers className="w-4 h-4 text-purple-400" />
            <h3 className="text-sm font-semibold text-white">Architecture Layers</h3>
          </div>

          {architectureLayers.length > 0 ? (
            <div className="grid grid-cols-2 gap-3">
              {architectureLayers.map((layer, idx) => (
                <div
                  key={idx}
                  className="p-3.5 rounded-xl glass-card border border-white/5 flex flex-col justify-between"
                >
                  <div className="font-semibold text-xs text-white">{layer.name}</div>
                  <div className="text-xs font-mono text-cyan-400 mt-2">
                    {layer.files} files
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-slate-500 py-4">No architecture layers detected yet.</div>
          )}
        </div>
      </div>

      {/* Tech Stack Pills */}
      <div className="glass-panel p-5 rounded-2xl border border-white/10 space-y-4">
        <div className="flex items-center space-x-2">
          <Sparkles className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-semibold text-white">Detected Tech Stack &amp; Libraries</h3>
        </div>
        <div className="flex flex-wrap gap-2">
          {(
            summary.tech_stack || [
              'JavaScript',
              'React',
              'Node.js',
              'Express',
              'Tailwind',
              'MongoDB/Mongoose',
              'JWT',
              'Vite',
            ]
          ).map((tech, idx) => (
            <span
              key={idx}
              className="px-3 py-1.5 rounded-lg bg-slate-800/80 border border-white/10 text-xs font-medium text-slate-200 shadow-sm"
            >
              {tech}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};
