import React, { useState } from 'react';
import { X, FolderGit2, Check, AlertCircle, Loader2, Trash2 } from 'lucide-react';
import type { RepositoryItem } from '../../types';

interface RepoModalProps {
  isOpen: boolean;
  onClose: () => void;
  repositories: RepositoryItem[];
  activeRepoId?: string;
  onSelectRepo: (id: string) => Promise<void>;
  onAnalyzeRepo: (pathOrUrl: string) => Promise<void>;
  onDeleteRepo?: (id: string) => Promise<void>;
}

export const RepoModal: React.FC<RepoModalProps> = ({
  isOpen,
  onClose,
  repositories,
  activeRepoId,
  onSelectRepo,
  onAnalyzeRepo,
  onDeleteRepo,
}) => {
  const [repoPathInput, setRepoPathInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoPathInput.trim()) return;
    setIsLoading(true);
    setError(null);
    try {
      await onAnalyzeRepo(repoPathInput.trim());
      setRepoPathInput('');
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to analyze repository');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelect = async (id: string) => {
    if (id === activeRepoId) {
      onClose();
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      await onSelectRepo(id);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to switch repository');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: string, name: string) => {
    e.stopPropagation();
    if (!window.confirm(`Are you sure you want to remove "${name}" from CodeCompass?`)) return;
    setIsLoading(true);
    setError(null);
    try {
      if (onDeleteRepo) {
        await onDeleteRepo(id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to remove repository');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="glass-panel w-full max-w-lg rounded-2xl border border-white/10 p-6 shadow-2xl relative">
        <button
          onClick={onClose}
          disabled={isLoading}
          className="absolute top-5 right-5 text-slate-400 hover:text-white transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center space-x-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
            <FolderGit2 className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-white">Repository Switcher</h3>
            <p className="text-xs text-slate-400">Select active repository or analyze a new one</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Existing Repositories */}
        <div className="mb-6">
          <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-2">
            Available Repositories ({repositories.length})
          </label>
          <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
            {repositories.map((repo) => {
              const isActive = repo.id === activeRepoId;
              return (
                <div
                  key={repo.id}
                  onClick={() => !isLoading && handleSelect(repo.id)}
                  className={`p-3 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                    isActive
                      ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-200'
                      : 'glass-card border-white/5 text-slate-300 hover:border-cyan-500/20 hover:text-white'
                  }`}
                >
                  <div className="truncate mr-3">
                    <div className="text-sm font-semibold truncate flex items-center space-x-2">
                      <span>{repo.name}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-slate-400 font-mono">
                        {repo.source}
                      </span>
                    </div>
                    <div className="text-xs text-slate-500 truncate mt-0.5">{repo.root_path}</div>
                  </div>
                  <div className="flex items-center space-x-2 flex-shrink-0">
                    {isActive && <Check className="w-4 h-4 text-cyan-400" />}
                    <button
                      type="button"
                      onClick={(e) => handleDelete(e, repo.id, repo.name)}
                      disabled={isLoading}
                      title={`Remove "${repo.name}" from CodeCompass`}
                      className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Import New Repository Form */}
        <form onSubmit={handleSubmit} className="border-t border-white/10 pt-4">
          <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-2">
            Analyze Local Path or GitHub URL
          </label>
          <div className="flex space-x-2">
            <input
              type="text"
              value={repoPathInput}
              onChange={(e) => setRepoPathInput(e.target.value)}
              placeholder="e.g. D:\Projects\MyApp or https://github.com/org/repo"
              disabled={isLoading}
              className="flex-1 bg-slate-900/80 border border-white/10 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
            />
            <button
              type="submit"
              disabled={isLoading || !repoPathInput.trim()}
              className="px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 font-semibold text-xs transition-all flex items-center space-x-1.5"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Analyzing...</span>
                </>
              ) : (
                <span>Analyze</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

