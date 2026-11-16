import React from 'react';
import {
  Compass,
  Layers,
  Network,
  FolderTree,
  GitFork,
  ShieldAlert,
  GraduationCap,
  MessageSquare,
  Sparkles,
  Route,
} from 'lucide-react';
import type { RepositoryItem } from '../../types';

export type NavTab =
  | 'overview'
  | 'graph'
  | 'files'
  | 'apis'
  | 'flows'
  | 'impact'
  | 'onboarding'
  | 'chat';

interface SidebarProps {
  currentTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  activeRepo?: RepositoryItem;
  aiModel?: string | null;
  onOpenSwitchRepo: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  activeRepo,
  aiModel,
  onOpenSwitchRepo,
}) => {
  const navItems: Array<{ id: NavTab; label: string; icon: React.FC<any>; badge?: string }> = [
    { id: 'overview', label: 'Overview', icon: Layers },
    { id: 'graph', label: 'Dependency Graph', icon: Network },
    { id: 'files', label: 'File Explorer', icon: FolderTree },
    { id: 'apis', label: 'API Map', icon: Route },
    { id: 'flows', label: 'Feature Flows', icon: GitFork },
    { id: 'impact', label: 'Impact Analysis', icon: ShieldAlert },
    { id: 'onboarding', label: 'Onboarding Guide', icon: GraduationCap },
    { id: 'chat', label: 'Ask AI Copilot', icon: MessageSquare, badge: 'Gemini' },
  ];

  return (
    <aside className="w-64 flex-shrink-0 flex flex-col justify-between glass-panel border-r border-white/5 bg-[#0c101d]/95 h-screen sticky top-0 z-20 select-none">
      <div className="flex flex-col h-full overflow-y-auto">
        {/* Brand Header */}
        <div className="p-5 border-b border-white/5 flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 ring-1 ring-white/20">
            <Compass className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
              CodeCompass
            </h1>
            <p className="text-[10px] font-semibold text-cyan-400/80 tracking-widest uppercase">
              Intelligence Platform
            </p>
          </div>
        </div>

        {/* Workspace Card */}
        <div className="p-4 border-b border-white/5">
          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
            Current Repository
          </div>
          <div className="glass-card p-3 rounded-lg border border-white/5 flex flex-col space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-sm text-slate-100 truncate">
                {activeRepo?.name || 'No Repository'}
              </span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 font-mono border border-cyan-500/20">
                {activeRepo?.source === 'github' ? 'GIT' : activeRepo?.name ? 'LOCAL' : 'EMPTY'}
              </span>
            </div>
            <button
              onClick={onOpenSwitchRepo}
              className="text-xs text-left text-cyan-400 hover:text-cyan-300 transition-colors flex items-center space-x-1 font-medium pt-1"
            >
              <span>+ Switch / Import Repo</span>
            </button>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="p-3 space-y-1 flex-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 shadow-lg shadow-cyan-500/10'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
                }`}
              >
                <div className="flex items-center space-x-3 min-w-0">
                  <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                  <span className="truncate whitespace-nowrap">{item.label}</span>
                </div>
                {item.badge && (
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded font-mono ml-2 flex-shrink-0 ${
                      isActive
                        ? 'bg-cyan-400/20 text-cyan-200'
                        : 'bg-white/5 text-slate-400'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Footer Info */}
        <div className="p-4 border-t border-white/5 space-y-2 text-[11px] text-slate-400">
          <div className="flex items-center justify-between">
            <span className="flex items-center space-x-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="font-medium text-slate-300">SQLite WAL</span>
            </span>
            <span className="font-mono text-slate-400 text-[10px]">v0.3.0</span>
          </div>
          {aiModel && (
            <div className="flex items-center space-x-1.5 text-cyan-400/80 bg-cyan-950/30 px-2 py-1 rounded border border-cyan-800/30 truncate">
              <Sparkles className="w-3 h-3 flex-shrink-0" />
              <span className="truncate font-mono text-[10px]">{aiModel}</span>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};
