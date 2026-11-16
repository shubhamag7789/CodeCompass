import React, { useState, useEffect } from 'react';
import { Sidebar, type NavTab } from './components/layout/Sidebar';
import { Topbar } from './components/layout/Topbar';
import { RepoModal } from './components/layout/RepoModal';
import { OverviewView } from './components/overview/OverviewView';
import { DependencyGraph } from './components/graph/DependencyGraph';
import { FileExplorer } from './components/files/FileExplorer';
import { ApiMapView } from './components/apis/ApiMapView';
import { ImpactExplorer } from './components/impact/ImpactExplorer';
import { FlowTracer } from './components/flows/FlowTracer';
import { OnboardingGuide } from './components/guide/OnboardingGuide';
import { CopilotChat } from './components/chat/CopilotChat';
import { AuthPage } from './components/auth/AuthPage';
import { api } from './api/client';
import type {
  AnalysisData,
  RepositoryItem,
  AiStatus,
  User,
} from './types';
import { Loader2, AlertCircle, FolderPlus, Plus } from 'lucide-react';

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [isAuthChecking, setIsAuthChecking] = useState<boolean>(true);

  const [currentTab, setCurrentTab] = useState<NavTab>('overview');
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [repositories, setRepositories] = useState<RepositoryItem[]>([]);
  const [activeRepoId, setActiveRepoId] = useState<string>('default');
  const [aiStatus, setAiStatus] = useState<AiStatus | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [isRepoModalOpen, setIsRepoModalOpen] = useState<boolean>(false);
  const [impactTargetNodeId, setImpactTargetNodeId] = useState<string | undefined>();
  const [chatPrefillPrompt, setChatPrefillPrompt] = useState<string>('');
  const [targetFile, setTargetFile] = useState<string | undefined>();

  // Check auth session on startup
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const user = await api.getCurrentUser();
        if (user) {
          setCurrentUser(user);
          await loadData();
        }
      } catch (err) {
        console.error('Session check failed:', err);
      } finally {
        setIsAuthChecking(false);
      }
    };
    checkAuth();
  }, []);

  const loadData = async (repoId?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const [aiRes, reposRes] = await Promise.all([
        api.getAiStatus().catch(() => null),
        api.getRepositories().catch(() => ({ active_repo_id: '', repositories: [] })),
      ]);

      if (aiRes) setAiStatus(aiRes);
      const userRepos = reposRes?.repositories || [];
      setRepositories(userRepos);

      if (userRepos.length > 0) {
        const targetId = repoId || (userRepos.some((r) => r.id === reposRes.active_repo_id) ? reposRes.active_repo_id : userRepos[0].id);
        setActiveRepoId(targetId);
        try {
          const analysisRes = await api.getAnalysis(targetId);
          setAnalysis(analysisRes);
        } catch {
          setAnalysis(null);
        }
      } else {
        setActiveRepoId('');
        setAnalysis(null);
      }
    } catch (err: any) {
      console.error('Error loading CodeCompass data:', err);
      setError(err.message || 'Failed to connect to CodeCompass backend.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAuthSuccess = async (user: User) => {
    setCurrentUser(user);
    await loadData();
  };

  const handleLogout = async () => {
    await api.logout();
    setCurrentUser(null);
    setAnalysis(null);
    setRepositories([]);
  };

  const handleSelectRepo = async (repoId: string) => {
    setTargetFile(undefined);
    setImpactTargetNodeId(undefined);
    await api.switchRepository(repoId);
    await loadData(repoId);
  };

  const handleDeleteRepo = async (repoId: string) => {
    setTargetFile(undefined);
    setImpactTargetNodeId(undefined);
    try {
      const res = await api.deleteRepository(repoId);
      setRepositories(res.repositories || []);
      if (res.active_repo_id) {
        setActiveRepoId(res.active_repo_id);
        await loadData(res.active_repo_id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to remove repository');
    }
  };

  const handleAnalyzeRepo = async (pathOrUrl: string) => {
    setTargetFile(undefined);
    setImpactTargetNodeId(undefined);
    const res = await api.analyzeRepository(pathOrUrl);
    const targetId = res.active_repo_id || (res as any).repo_id;
    setAnalysis(res);
    if (targetId) {
      setActiveRepoId(targetId);
    }
    await loadData(targetId);
  };

  const handleInspectImpact = (nodeId: string) => {
    setImpactTargetNodeId(nodeId);
    setCurrentTab('impact');
  };

  const handleAskAiBlastRadius = (targetLabel: string, risk: string) => {
    setChatPrefillPrompt(
      `Please conduct an in-depth blast radius and regression risk analysis for symbol "${targetLabel}". It has a computed ${risk} risk level. What should I test and verify before changing it?`
    );
    setCurrentTab('chat');
  };

  const handleOpenFile = (filePath: string) => {
    setTargetFile(filePath);
    setCurrentTab('files');
  };

  // 1. Initial security check loading screen
  if (isAuthChecking) {
    return (
      <div className="min-h-screen bg-[#070a14] flex flex-col items-center justify-center space-y-4 text-slate-400">
        <Loader2 className="w-9 h-9 animate-spin text-cyan-400" />
        <div className="text-sm font-semibold tracking-wide text-slate-300">
          Verifying security session...
        </div>
      </div>
    );
  }

  // 2. Authentication Page when not signed in
  if (!currentUser) {
    return <AuthPage onAuthSuccess={handleAuthSuccess} />;
  }

  const activeRepo = repositories.find((r) => r.id === activeRepoId) || (repositories.length > 0 ? repositories[0] : {
    id: '',
    name: '',
    root_path: '.',
    source: 'local' as const,
  });

  const fileList = (analysis?.files || []).map((f) => (typeof f === 'string' ? f : f.path));

  return (
    <div className="flex min-h-screen bg-[#0c101d] text-slate-100 font-sans selection:bg-cyan-500/20 selection:text-cyan-200">
      {/* Sidebar Navigation */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        activeRepo={activeRepo}
        aiModel={aiStatus?.model}
        onOpenSwitchRepo={() => setIsRepoModalOpen(true)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Topbar
          headline={analysis?.summary?.headline}
          repoName={activeRepo?.name}
          aiStatus={aiStatus}
          currentUser={currentUser}
          onOpenImport={() => setIsRepoModalOpen(true)}
          onLogout={handleLogout}
        />

        <main className="flex-1">
          {isLoading && !analysis && repositories.length > 0 ? (
            <div className="h-[70vh] flex flex-col items-center justify-center space-y-3 text-slate-400">
              <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
              <div className="text-sm font-medium">Loading CodeCompass intelligence graph...</div>
            </div>
          ) : repositories.length === 0 ? (
            <div className="h-[75vh] flex flex-col items-center justify-center text-center p-8 max-w-lg mx-auto space-y-6">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-blue-600/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-xl shadow-cyan-500/10 ring-1 ring-white/10">
                <FolderPlus className="w-8 h-8" />
              </div>
              <div className="space-y-2">
                <h2 className="text-xl font-bold text-white tracking-tight">Welcome to CodeCompass</h2>
                <p className="text-xs text-slate-400 leading-relaxed max-w-md">
                  Your workspace is clean and empty. Import a local directory or paste a public GitHub repository link to begin deep architectural analysis.
                </p>
              </div>
              <button
                onClick={() => setIsRepoModalOpen(true)}
                className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-semibold text-xs shadow-lg shadow-cyan-500/20 active:scale-95 transition-all"
              >
                <Plus className="w-4 h-4" />
                <span>Import Your First Repository</span>
              </button>
            </div>
          ) : error ? (
            <div className="max-w-2xl mx-auto mt-16 p-6 rounded-2xl glass-panel border border-red-500/30 text-center space-y-4">
              <div className="w-12 h-12 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 mx-auto flex items-center justify-center">
                <AlertCircle className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-white">Connection or Analysis Error</h3>
              <p className="text-xs text-red-300">{error}</p>
              <button
                onClick={() => loadData(activeRepoId)}
                className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-xs font-semibold text-white transition-all"
              >
                Retry
              </button>
            </div>
          ) : analysis ? (
            <div className="h-full relative">
              <div className={currentTab === 'overview' ? 'block' : 'hidden'}>
                <OverviewView
                  key={activeRepoId}
                  analysis={analysis}
                  onNavigate={setCurrentTab}
                  onOpenFile={handleOpenFile}
                />
              </div>
              <div className={currentTab === 'graph' ? 'h-full' : 'hidden'}>
                <DependencyGraph
                  key={activeRepoId}
                  analysis={analysis}
                  onSelectImpactNode={handleInspectImpact}
                  onOpenFile={handleOpenFile}
                  activeRepoId={activeRepoId}
                />
              </div>
              <div className={currentTab === 'files' ? 'h-full' : 'hidden'}>
                <FileExplorer
                  key={activeRepoId}
                  files={fileList}
                  activeRepoId={activeRepoId}
                  selectedFile={targetFile}
                  onSelectFile={(f) => setTargetFile(f)}
                />
              </div>
              <div className={currentTab === 'apis' ? 'block' : 'hidden'}>
                <ApiMapView
                  key={activeRepoId}
                  apis={analysis.apis || []}
                  onOpenFile={handleOpenFile}
                />
              </div>
              <div className={currentTab === 'impact' ? 'h-full' : 'hidden'}>
                <ImpactExplorer
                  key={activeRepoId}
                  analysis={analysis}
                  activeRepoId={activeRepoId}
                  initialNodeId={impactTargetNodeId}
                  onAskAiBlastRadius={handleAskAiBlastRadius}
                  onNavigateToGraph={() => setCurrentTab('graph')}
                  onOpenFile={handleOpenFile}
                />
              </div>
              <div className={currentTab === 'flows' ? 'block' : 'hidden'}>
                <FlowTracer
                  key={activeRepoId}
                  activeRepoId={activeRepoId}
                  onSelectFile={handleOpenFile}
                />
              </div>
              <div className={currentTab === 'onboarding' ? 'block' : 'hidden'}>
                <OnboardingGuide
                  key={activeRepoId}
                  activeRepoId={activeRepoId}
                  onSelectFile={handleOpenFile}
                />
              </div>
              <div className={currentTab === 'chat' ? 'h-full' : 'hidden'}>
                <CopilotChat
                  key={activeRepoId}
                  activeRepoId={activeRepoId}
                  aiStatus={aiStatus}
                  onSelectFile={handleOpenFile}
                  prefilledPrompt={chatPrefillPrompt}
                />
              </div>
            </div>
          ) : null}
        </main>
      </div>

      {/* Repository Switch / Import Modal */}
      <RepoModal
        isOpen={isRepoModalOpen}
        onClose={() => setIsRepoModalOpen(false)}
        repositories={repositories}
        activeRepoId={activeRepoId}
        onSelectRepo={handleSelectRepo}
        onAnalyzeRepo={handleAnalyzeRepo}
        onDeleteRepo={handleDeleteRepo}
      />
    </div>
  );
};

export default App;
