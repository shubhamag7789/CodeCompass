import React, { useState, useMemo } from 'react';
import { Network, Search, Filter, FileText, ArrowRight, ExternalLink } from 'lucide-react';
import type { ApiEndpoint } from '../../types';

interface ApiMapViewProps {
  apis: ApiEndpoint[];
  onOpenFile: (filePath: string) => void;
}

export const ApiMapView: React.FC<ApiMapViewProps> = ({ apis = [], onOpenFile }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedMethod, setSelectedMethod] = useState<string>('ALL');

  const filteredApis = useMemo(() => {
    return apis.filter((api) => {
      if (selectedMethod !== 'ALL' && api.method.toUpperCase() !== selectedMethod) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const hay = `${api.method} ${api.path} ${api.file || ''} ${api.handler || ''}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [apis, searchQuery, selectedMethod]);

  const methodColors: Record<string, string> = {
    GET: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    POST: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    PUT: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    PATCH: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
    DELETE: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
  };

  const methods = ['ALL', 'GET', 'POST', 'PUT', 'DELETE'];

  return (
    <div className="space-y-6 max-w-7xl mx-auto p-6">
      {/* Header */}
      <div className="glass-panel p-5 rounded-2xl border border-white/10 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
            <Network className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white tracking-tight">
              HTTP API Surface &amp; Route Registry
            </h2>
            <p className="text-xs text-slate-400">
              Discovered REST endpoints, middleware handlers, and source route controllers
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-xs font-mono px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
            {filteredApis.length} of {apis.length} Endpoints
          </span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="glass-panel p-4 rounded-xl border border-white/10 flex flex-wrap items-center justify-between gap-3">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-3.5 h-3.5 absolute left-3 top-3 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search API by path, method, controller..."
            className="w-full bg-slate-900/80 border border-white/10 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
          />
        </div>

        <div className="flex items-center space-x-1.5">
          {methods.map((m) => (
            <button
              key={m}
              onClick={() => setSelectedMethod(m)}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all ${
                selectedMethod === m
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                  : 'bg-white/5 text-slate-400 hover:text-slate-200 hover:bg-white/10 border border-white/5'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      {/* API Table / Card Grid */}
      <div className="glass-panel rounded-2xl border border-white/10 overflow-hidden">
        <div className="divide-y divide-white/5">
          {filteredApis.length > 0 ? (
            filteredApis.map((api, idx) => {
              const methodKey = api.method.toUpperCase();
              const badgeStyle =
                methodColors[methodKey] || 'bg-slate-800 text-slate-300 border-slate-700';

              return (
                <div
                  key={idx}
                  className="p-4 hover:bg-white/[0.02] transition-colors flex flex-col md:flex-row md:items-center justify-between gap-3"
                >
                  <div className="flex items-center space-x-3 truncate">
                    <span
                      className={`text-[11px] font-mono font-bold px-2.5 py-1 rounded-md border flex-shrink-0 ${badgeStyle}`}
                    >
                      {methodKey}
                    </span>
                    <span className="font-mono text-sm font-semibold text-white tracking-wide truncate">
                      {api.path}
                    </span>
                  </div>

                  <div className="flex items-center space-x-4 flex-shrink-0 text-xs">
                    {api.handler && (
                      <span className="font-mono text-slate-400 text-[11px] bg-slate-900/60 px-2 py-1 rounded border border-white/5 truncate max-w-xs">
                        handler: {api.handler}
                      </span>
                    )}

                    {api.file && (
                      <button
                        onClick={() => onOpenFile(api.file!)}
                        className="group flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 font-mono text-[11px] transition-all"
                        title="Open controller file in File Explorer"
                      >
                        <FileText className="w-3.5 h-3.5 text-cyan-400" />
                        <span className="truncate max-w-[200px]">
                          {api.file}
                          {api.line ? `:${api.line}` : ''}
                        </span>
                        <ExternalLink className="w-3 h-3 text-cyan-400/70 group-hover:text-cyan-300" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="p-12 text-center text-slate-400 text-xs">
              No matching API endpoints found for &ldquo;{searchQuery}&rdquo;.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

