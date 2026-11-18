import React, { useState, useRef, useEffect } from 'react';
import {
  Plus,
  Sparkles,
  Terminal,
  LogOut,
  ChevronDown,
  ShieldCheck,
  CheckCircle2,
  X,
  KeyRound,
  Copy,
  RefreshCw,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { api } from '../../api/client';
import type { AiStatus, User } from '../../types';

interface TopbarProps {
  headline?: string;
  repoName?: string;
  aiStatus?: AiStatus | null;
  currentUser?: User | null;
  onOpenImport: () => void;
  onLogout?: () => void;
}

const DEFAULT_QUESTIONS = [
  'What was the name of your first school or college?',
  'What city or town was your mother or father born in?',
  'What was the name of your first pet?',
  'What was the make and model of your first car or bike?',
  'What was your childhood nickname?',
  'What is your favorite programming language or editor?',
];

const RECOVERY_WORDS = [
  'anchor', 'beacon', 'breeze', 'canyon', 'castle', 'cipher', 'comet', 'compass',
  'crater', 'crystal', 'delta', 'eagle', 'ember', 'falcon', 'forest', 'galaxy',
  'glacier', 'harbor', 'horizon', 'island', 'jasper', 'jungle', 'jupiter', 'lagoon',
  'matrix', 'meteor', 'nebula', 'nexus', 'oasis', 'orbit', 'phoenix', 'planet',
  'prism', 'pulsar', 'quantum', 'radar', 'river', 'rocket', 'shadow', 'shield',
  'sierra', 'signal', 'silver', 'solar', 'stream', 'summit', 'timber', 'topaz',
  'torrent', 'valley', 'vector', 'vertex', 'vortex', 'voyage', 'zenith',
];

function generatePassphrase(): string {
  const words: string[] = [];
  for (let i = 0; i < 4; i++) {
    words.push(RECOVERY_WORDS[Math.floor(Math.random() * RECOVERY_WORDS.length)]);
  }
  return words.join('-');
}

export const Topbar: React.FC<TopbarProps> = ({
  headline,
  repoName,
  aiStatus,
  currentUser,
  onOpenImport,
  onLogout,
}) => {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isSecurityModalOpen, setIsSecurityModalOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Security Modal state
  const [selectedQuestion, setSelectedQuestion] = useState(DEFAULT_QUESTIONS[0]);
  const [customQuestion, setCustomQuestion] = useState('');
  const [securityAnswer, setSecurityAnswer] = useState('');
  const [recoveryPassphrase, setRecoveryPassphrase] = useState('');
  const [copiedPassphrase, setCopiedPassphrase] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [modalSuccess, setModalSuccess] = useState<string | null>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleOpenSecurityModal = async () => {
    setIsDropdownOpen(false);
    setIsSecurityModalOpen(true);
    setModalError(null);
    setModalSuccess(null);
    setSecurityAnswer('');
    try {
      const data = await api.getSecuritySettings();
      if (data.security_question) {
        if (DEFAULT_QUESTIONS.includes(data.security_question)) {
          setSelectedQuestion(data.security_question);
        } else {
          setSelectedQuestion('CUSTOM');
          setCustomQuestion(data.security_question);
        }
      }
      setRecoveryPassphrase(generatePassphrase());
    } catch {
      setRecoveryPassphrase(generatePassphrase());
    }
  };

  const handleSaveSecuritySettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setModalError(null);
    setModalSuccess(null);

    const questionToSave = selectedQuestion === 'CUSTOM' ? customQuestion : selectedQuestion;
    if (!questionToSave.trim()) {
      setModalError('Please select or specify a security question.');
      return;
    }
    if (!securityAnswer.trim()) {
      setModalError('Please enter your security answer.');
      return;
    }

    setIsSaving(true);
    try {
      await api.updateSecuritySettings({
        security_question: questionToSave.trim(),
        security_answer: securityAnswer.trim(),
        recovery_passphrase: recoveryPassphrase.trim() || undefined,
      });
      setModalSuccess('Security recovery question and passphrase updated successfully!');
      setTimeout(() => {
        setIsSecurityModalOpen(false);
      }, 1500);
    } catch (err: any) {
      setModalError(err.message || 'Failed to update security settings.');
    } finally {
      setIsSaving(false);
    }
  };

  const initials = currentUser?.name
    ? currentUser.name
        .split(' ')
        .map((p) => p[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'U';

  return (
    <>
      <header className="h-16 border-b border-white/5 bg-[#0c101d]/80 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center space-x-3 truncate mr-4">
          <div className="flex flex-col truncate">
            <div className="text-[10px] font-bold text-cyan-400/90 tracking-widest uppercase flex items-center space-x-1.5">
              <span>Codebase Intelligence</span>
              {repoName && (
                <>
                  <span className="text-slate-600">/</span>
                  <span className="text-slate-400 font-mono lowercase">{repoName}</span>
                </>
              )}
            </div>
            <div className="text-sm font-bold font-futuristic-gradient truncate">
              {headline || 'Service-oriented architecture and dependency analysis.'}
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3 flex-shrink-0">
          {/* AI Provider Badge */}
          {aiStatus?.configured ? (
            <div className="hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-xs text-cyan-300 font-medium">
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
              <span className="capitalize">{aiStatus.provider || 'Gemini'}</span>
              <span className="text-slate-500">|</span>
              <span className="font-mono text-[11px] text-cyan-200">{aiStatus.model || '3.5-flash-lite'}</span>
            </div>
          ) : (
            <div className="hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-full bg-slate-800/60 border border-white/10 text-xs text-slate-400">
              <Terminal className="w-3.5 h-3.5 text-slate-400" />
              <span>Local Mode</span>
            </div>
          )}

          {/* Import Repo Button */}
          <button
            onClick={onOpenImport}
            className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-medium text-xs shadow-lg shadow-blue-500/20 transition-all active:scale-95"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Import Repository</span>
          </button>

          {/* User Profile Dropdown */}
          {currentUser && (
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                className="flex items-center space-x-3 py-1.5 px-3 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 hover:border-cyan-500/30 transition-all text-left shadow-sm group"
              >
                <div className="hidden sm:flex flex-col text-right">
                  <span className="text-xs font-semibold text-slate-100 truncate max-w-[140px] leading-tight">
                    {currentUser.name}
                  </span>
                  <div className="mt-1 flex justify-end">
                    <span className="text-[9px] font-mono uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 leading-none">
                      {currentUser.role}
                    </span>
                  </div>
                </div>
                <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-600 to-blue-600 flex items-center justify-center text-white font-bold text-xs shadow-md shadow-cyan-500/20 ring-1 ring-white/20 flex-shrink-0">
                  {initials}
                </div>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-200 transition-colors flex-shrink-0" />
              </button>

              {isDropdownOpen && (
                <div className="absolute right-0 mt-2 w-64 rounded-xl bg-[#0e1426] border border-white/10 shadow-2xl p-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
                  <div className="p-3 border-b border-white/5 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-white truncate">{currentUser.name}</span>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                        {currentUser.role}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 truncate">{currentUser.email}</div>
                    <div className="flex items-center space-x-1 text-[10px] text-emerald-400 pt-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                      <span>Workspace Data Isolated</span>
                    </div>
                  </div>

                  <div className="p-1 border-b border-white/5">
                    <button
                      onClick={handleOpenSecurityModal}
                      className="w-full flex items-center space-x-2 px-3 py-2 rounded-lg text-xs font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-colors"
                    >
                      <ShieldCheck className="w-4 h-4 text-cyan-400" />
                      <span>Security & Recovery</span>
                    </button>
                  </div>

                  <div className="p-1 pt-1.5">
                    <button
                      onClick={() => {
                        setIsDropdownOpen(false);
                        if (onLogout) onLogout();
                      }}
                      className="w-full flex items-center space-x-2 px-3 py-2 rounded-lg text-xs font-medium text-red-300 hover:text-red-200 hover:bg-red-500/10 transition-colors"
                    >
                      <LogOut className="w-4 h-4" />
                      <span>Sign Out</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </header>

      {/* Security Settings Modal */}
      {isSecurityModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-[#0e1426] border border-white/10 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-5 relative">
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <div className="flex items-center space-x-2 text-cyan-400">
                <ShieldCheck className="w-5 h-5" />
                <h3 className="text-sm font-bold text-white">Security & Recovery Settings</h3>
              </div>
              <button
                onClick={() => setIsSecurityModalOpen(false)}
                className="text-slate-400 hover:text-white transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {modalError && (
              <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                <span>{modalError}</span>
              </div>
            )}

            {modalSuccess && (
              <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>{modalSuccess}</span>
              </div>
            )}

            <form onSubmit={handleSaveSecuritySettings} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">
                  Select Security Question
                </label>
                <select
                  value={selectedQuestion}
                  onChange={(e) => setSelectedQuestion(e.target.value)}
                  className="w-full px-3 py-2 bg-[#0a0f1d] border border-white/10 rounded-xl text-xs text-white focus:outline-none focus:border-cyan-500"
                >
                  {DEFAULT_QUESTIONS.map((q) => (
                    <option key={q} value={q} className="bg-[#0a0f1d] text-white">
                      {q}
                    </option>
                  ))}
                  <option value="CUSTOM" className="bg-[#0a0f1d] text-cyan-300">
                    + Write custom question...
                  </option>
                </select>

                {selectedQuestion === 'CUSTOM' && (
                  <input
                    type="text"
                    required
                    value={customQuestion}
                    onChange={(e) => setCustomQuestion(e.target.value)}
                    placeholder="Enter your custom security question"
                    className="w-full mt-2 px-3 py-2 bg-black/40 border border-white/10 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                  />
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">
                  Your Security Answer (case-insensitive)
                </label>
                <input
                  type="text"
                  required
                  value={securityAnswer}
                  onChange={(e) => setSecurityAnswer(e.target.value)}
                  placeholder="e.g. Lincoln High School"
                  className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
                <span className="text-[10px] text-slate-400">
                  Answers are securely salted and hashed with PBKDF2 SHA-256.
                </span>
              </div>

              {/* 4-Word Recovery Passphrase */}
              <div className="space-y-2 pt-2 border-t border-white/10">
                <div className="flex items-center justify-between text-xs text-slate-300">
                  <span className="font-semibold">4-Word Recovery Passphrase</span>
                  <button
                    type="button"
                    onClick={() => setRecoveryPassphrase(generatePassphrase())}
                    className="text-slate-400 hover:text-cyan-300 text-[11px] flex items-center space-x-1"
                  >
                    <RefreshCw className="w-3 h-3" />
                    <span>Generate New</span>
                  </button>
                </div>

                <div className="flex items-center space-x-2">
                  <div className="flex-1 font-mono text-xs px-3 py-2 rounded-xl bg-black/60 border border-cyan-500/20 text-cyan-300 select-all truncate">
                    {recoveryPassphrase}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(recoveryPassphrase);
                      setCopiedPassphrase(true);
                      setTimeout(() => setCopiedPassphrase(false), 2000);
                    }}
                    className="px-3 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-slate-200 flex items-center space-x-1"
                  >
                    {copiedPassphrase ? (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-[11px] text-emerald-300">Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5 text-slate-300" />
                        <span className="text-[11px]">Copy</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-white/10">
                <button
                  type="button"
                  onClick={() => setIsSecurityModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs text-slate-400 hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSaving}
                  className="px-4 py-2 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-semibold text-xs shadow-lg shadow-cyan-500/20 transition-all flex items-center space-x-1.5 disabled:opacity-50"
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Save Security Settings</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
};
