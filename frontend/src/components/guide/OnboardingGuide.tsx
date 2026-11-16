import React, { useState, useEffect, useMemo } from 'react';
import {
  GraduationCap,
  Compass,
  FileCode,
  FileText,
  AlertCircle,
  CheckCircle,
  Layers,
  ArrowRight,
  BookOpen,
  Loader2,
  Server,
  Layout,
  ShieldCheck,
  ExternalLink,
  Flame,
  CheckSquare,
  Square,
  Sparkles,
  Trophy,
  RotateCcw,
} from 'lucide-react';
import { api } from '../../api/client';
import type { RoleGuide, ReadingStep } from '../../types';

interface OnboardingGuideProps {
  activeRepoId?: string;
  onSelectFile?: (filePath: string) => void;
}

export const OnboardingGuide: React.FC<OnboardingGuideProps> = ({
  activeRepoId,
  onSelectFile,
}) => {
  const [guides, setGuides] = useState<Record<string, RoleGuide>>({});
  const [selectedRole, setSelectedRole] = useState<string>('fullstack');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [activeChecklistDay, setActiveChecklistDay] = useState<number>(1);
  const [completedTasks, setCompletedTasks] = useState<Record<string, boolean>>({});

  // Unique storage key for persisting progress
  const storageKey = useMemo(() => {
    return `codecompass_onboarding_v2_${activeRepoId || 'default'}_${selectedRole}`;
  }, [activeRepoId, selectedRole]);

  // Load saved progress from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        setCompletedTasks(JSON.parse(saved));
      } else {
        setCompletedTasks({});
      }
    } catch {
      setCompletedTasks({});
    }
  }, [storageKey]);

  // Save progress to localStorage on change
  const toggleTask = (taskKey: string) => {
    setCompletedTasks((prev) => {
      const updated = {
        ...prev,
        [taskKey]: !prev[taskKey],
      };
      try {
        localStorage.setItem(storageKey, JSON.stringify(updated));
      } catch (err) {
        console.error('Failed to save onboarding progress:', err);
      }
      return updated;
    });
  };

  const handleResetProgress = () => {
    setCompletedTasks({});
    try {
      localStorage.removeItem(storageKey);
    } catch {}
  };

  useEffect(() => {
    let isCurrent = true;
    setIsLoading(true);

    api
      .getOnboardingGuides(activeRepoId)
      .then((res) => {
        if (!isCurrent) return;
        const roles = res.roles || {};
        setGuides(roles);
        const keys = Object.keys(roles);
        if (keys.length > 0 && !roles[selectedRole]) {
          setSelectedRole(keys[0]);
        }
      })
      .catch((err) => console.error('Failed to load onboarding guides:', err))
      .finally(() => {
        if (isCurrent) setIsLoading(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [activeRepoId]);

  const activeGuide = guides[selectedRole];
  const roleKeys = Object.keys(guides);

  const getRoleIcon = (role: string) => {
    const r = role.toLowerCase();
    if (r.includes('back')) return <Server className="w-3.5 h-3.5" />;
    if (r.includes('front')) return <Layout className="w-3.5 h-3.5" />;
    if (r.includes('devops') || r.includes('qa')) return <ShieldCheck className="w-3.5 h-3.5" />;
    return <Layers className="w-3.5 h-3.5" />;
  };

  const getCategoryBadge = (cat?: string) => {
    const c = (cat || 'core').toLowerCase();
    let color = 'bg-slate-700/50 text-slate-300 border-slate-600';
    if (c === 'entrypoint') color = 'bg-amber-500/15 text-amber-300 border-amber-500/30';
    else if (c === 'core') color = 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30';
    else if (c === 'service') color = 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
    else if (c === 'data') color = 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30';
    else if (c === 'test') color = 'bg-purple-500/15 text-purple-300 border-purple-500/30';

    return (
      <span className={`text-[9px] font-mono font-bold uppercase px-2 py-0.5 rounded border ${color}`}>
        {cat || 'CORE'}
      </span>
    );
  };

  // Harmonize reading steps from reading_path or legacy learning_path
  const readingSteps: ReadingStep[] = useMemo(() => {
    if (!activeGuide) return [];
    if (activeGuide.reading_path && activeGuide.reading_path.length > 0) {
      return activeGuide.reading_path;
    }
    if (activeGuide.learning_path && activeGuide.learning_path.length > 0) {
      return activeGuide.learning_path.map((lp, idx) => ({
        day: idx + 1,
        title: lp.title,
        description: lp.description,
        file_path: lp.files && lp.files[0] ? lp.files[0] : '',
        category: 'core',
      }));
    }
    return [];
  }, [activeGuide]);

  // Group steps by Day
  const stepsByDay = useMemo(() => {
    const map = new Map<number, ReadingStep[]>();
    readingSteps.forEach((s) => {
      const d = s.day || 1;
      if (!map.has(d)) map.set(d, []);
      map.get(d)!.push(s);
    });
    return Array.from(map.entries()).sort((a, b) => a[0] - b[0]);
  }, [readingSteps]);

  // Core entry points
  const entrypoints = useMemo(() => {
    if (!activeGuide) return [];
    if (activeGuide.key_entrypoints && activeGuide.key_entrypoints.length > 0) {
      return activeGuide.key_entrypoints;
    }
    if (activeGuide.core_files && activeGuide.core_files.length > 0) {
      return activeGuide.core_files.map((cf) => ({
        path: cf.path,
        label: cf.path.split('/').pop() || cf.path,
        importance: cf.importance,
        rationale: cf.rationale,
      }));
    }
    return [];
  }, [activeGuide]);

  const importantApis = activeGuide?.important_apis || [];
  const highRiskComponents = activeGuide?.high_risk_components || [];

  const gotchas = activeGuide?.gotchas || [
    'Ensure environment variables and configuration files are properly set before starting local execution.',
    'Validate all input parameters, data types, and schemas prior to triggering state mutations.',
    'Handle asynchronous network errors and timeouts gracefully with proper error boundaries.',
  ];

  // Dynamic Multi-Day Action Tasks
  const multiDayTasks: Record<number, string[]> = useMemo(() => {
    const primaryEntry = entrypoints[0]?.path || readingSteps[0]?.file_path || 'application entry';
    const primaryApi = importantApis[0]
      ? `${importantApis[0].method} ${importantApis[0].path}`
      : (readingSteps[1]?.title || 'core endpoints');
    const primaryHighRisk = highRiskComponents[0]?.label || 'key architecture components';

    return {
      1: [
        `Review primary entry point (${primaryEntry}) to inspect application bootstrapping and routing.`,
        `Trace the primary API or workflow (${primaryApi}) from public entry to handler execution.`,
        'Verify local development configuration, runtime dependencies, and environment setup.',
      ],
      2: [
        'Inspect architectural contracts and interface boundaries across modules.',
        'Review controller and service domain logic, request validation rules, and error handling.',
        'Examine data schema models, persistence constraints, and query definitions.',
      ],
      3: [
        `Analyze blast-radius implications for key component "${primaryHighRisk}".`,
        'Run full unit and integration test suite to verify baseline codebase integrity.',
        'Simulate a code modification and inspect impacted downstream symbols in Impact Analysis.',
      ],
    };
  }, [entrypoints, readingSteps, importantApis, highRiskComponents]);

  // Compute Task Completion Metrics
  const allTaskKeys = useMemo(() => {
    const keys: string[] = [];
    [1, 2, 3].forEach((day) => {
      (multiDayTasks[day] || []).forEach((_, idx) => {
        keys.push(`day-${day}-task-${idx}`);
      });
    });
    return keys;
  }, [multiDayTasks]);

  const totalTasksCount = allTaskKeys.length;
  const completedTotalCount = allTaskKeys.filter((k) => completedTasks[k]).length;
  const overallPercentage = totalTasksCount > 0 ? Math.round((completedTotalCount / totalTasksCount) * 100) : 0;

  // Day-specific completion
  const currentDayTasks = multiDayTasks[activeChecklistDay] || [];
  const currentDayCompletedCount = currentDayTasks.filter((_, idx) => completedTasks[`day-${activeChecklistDay}-task-${idx}`]).length;
  const isCurrentDayFullyCompleted = currentDayTasks.length > 0 && currentDayCompletedCount === currentDayTasks.length;
  const isDay1Completed = (multiDayTasks[1] || []).every((_, idx) => completedTasks[`day-1-task-${idx}`]);

  // Dynamic Status Badge in Top Bar
  const getReadinessBadge = () => {
    if (overallPercentage === 100) {
      return {
        label: 'Fully Ramped Up (100%)',
        color: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 ring-1 ring-emerald-500/30',
        icon: <Trophy className="w-3.5 h-3.5 text-emerald-400" />,
      };
    }
    if (isDay1Completed) {
      return {
        label: `Day 1 Certified (${overallPercentage}%)`,
        color: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40 ring-1 ring-cyan-500/30',
        icon: <Sparkles className="w-3.5 h-3.5 text-cyan-400" />,
      };
    }
    if (completedTotalCount > 0) {
      return {
        label: `Day 1 In Progress (${completedTotalCount}/${totalTasksCount})`,
        color: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
        icon: <GraduationCap className="w-3.5 h-3.5 text-amber-400" />,
      };
    }
    return {
      label: 'Day 1 Ready (0% Done)',
      color: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
      icon: <GraduationCap className="w-3.5 h-3.5 text-emerald-400" />,
    };
  };

  const readinessBadge = getReadinessBadge();

  return (
    <div className="space-y-6 max-w-7xl mx-auto p-6">
      {/* Header Banner */}
      <div className="glass-panel p-6 rounded-2xl border border-white/10 relative overflow-hidden">
        <div className="absolute -right-20 -top-20 w-80 h-80 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none"></div>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-300 shadow-lg shadow-emerald-500/10">
              <GraduationCap className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-[10px] font-bold tracking-widest uppercase px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                  Developer Ramp-Up Curriculum
                </span>
                <span className="text-xs text-slate-400">Persona-Tailored Architecture</span>
              </div>
              <h2 className="text-2xl font-bold font-futuristic-gradient tracking-tight mt-1">
                Role-Based Onboarding &amp; Ramp-Up Engine
              </h2>
              <p className="text-xs text-slate-300 mt-1 max-w-2xl leading-relaxed">
                Accelerate team velocity with role-curated day-by-day reading sequences, core architectural
                entrypoints, critical API routes, and blast-radius rules customized by engineering focus.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2 self-start md:self-auto">
            <span
              className={`text-xs font-mono px-3.5 py-1.5 rounded-xl border font-bold shadow-sm flex items-center space-x-1.5 transition-all ${readinessBadge.color}`}
              title="Real-time onboarding readiness status"
            >
              {readinessBadge.icon}
              <span>{readinessBadge.label}</span>
            </span>
          </div>
        </div>
      </div>

      {/* Role Selection Tabs */}
      <div className="flex items-center space-x-2.5 overflow-x-auto pb-1">
        {(roleKeys.length > 0 ? roleKeys : ['fullstack', 'frontend', 'backend', 'devops_qa']).map(
          (role) => {
            const isActive = role === selectedRole;
            const label = role.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());
            return (
              <button
                key={role}
                onClick={() => setSelectedRole(role)}
                className={`px-4 py-2.5 rounded-xl border text-xs font-semibold whitespace-nowrap transition-all flex items-center space-x-2 ${
                  isActive
                    ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-200 shadow-lg shadow-emerald-500/10 ring-1 ring-emerald-500/30'
                    : 'glass-card border-white/5 text-slate-400 hover:text-white hover:border-emerald-500/30'
                }`}
              >
                <span className={isActive ? 'text-emerald-300' : 'text-slate-500'}>
                  {getRoleIcon(role)}
                </span>
                <span>{label}</span>
              </button>
            );
          }
        )}
      </div>

      {/* Main Content Area */}
      {isLoading ? (
        <div className="glass-panel p-16 rounded-2xl border border-white/10 flex flex-col items-center justify-center text-slate-400 space-y-3">
          <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
          <span className="text-sm font-medium">Synthesizing personalized role curriculum...</span>
        </div>
      ) : activeGuide ? (
        <div className="space-y-6">
          {/* Mission & Architectural Summary */}
          <div className="glass-panel p-6 rounded-2xl border border-white/10 space-y-3 relative overflow-hidden">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-white/5 pb-3">
              <div>
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-emerald-400">
                  Engineering Focus
                </span>
                <h3 className="text-lg font-bold font-futuristic-gradient">
                  {activeGuide.title || `${selectedRole.toUpperCase()} Architecture Curriculum`}
                </h3>
              </div>
              <span className="text-xs font-mono px-3 py-1 rounded-lg bg-white/5 border border-white/10 text-slate-300">
                {readingSteps.length} Curated Reading Milestones
              </span>
            </div>

            {activeGuide.mission && (
              <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-200 leading-relaxed font-medium">
                <span className="font-bold text-white mr-1.5">Mission:</span>
                {activeGuide.mission}
              </div>
            )}

            <p className="text-xs text-slate-300 leading-relaxed">
              {activeGuide.summary}
            </p>
          </div>

          {/* Grid: Reading Roadmap (Left 2 cols) vs Critical References (Right 1 col) */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left 2 Cols: Day-by-Day Reading Roadmap */}
            <div className="lg:col-span-2 glass-panel p-6 rounded-2xl border border-white/10 space-y-6">
              <div className="flex items-center justify-between border-b border-white/5 pb-3">
                <div className="flex items-center space-x-2">
                  <BookOpen className="w-4 h-4 text-emerald-400" />
                  <h4 className="text-sm font-bold uppercase tracking-wider text-white">
                    Day-by-Day Reading Roadmap
                  </h4>
                </div>
                <span className="text-[10px] font-mono text-slate-400">
                  Step-by-step codebase walkthrough
                </span>
              </div>

              {stepsByDay.length === 0 ? (
                <div className="p-8 text-center text-xs text-slate-400">
                  No reading steps available for this role.
                </div>
              ) : (
                <div className="space-y-6">
                  {stepsByDay.map(([dayNum, daySteps]) => (
                    <div key={dayNum} className="space-y-3">
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-mono font-bold px-2.5 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                          DAY {dayNum}
                        </span>
                        <span className="text-xs font-bold text-slate-200">
                          {dayNum === 1
                            ? 'System Bootstrapping & Entrypoints'
                            : dayNum === 2
                            ? 'Core Data Contracts & API Layer'
                            : 'Business Logic, Services & Persistence'}
                        </span>
                      </div>

                      <div className="relative pl-6 space-y-3.5 before:content-[''] before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-emerald-500/30">
                        {daySteps.map((step, idx) => (
                          <div key={idx} className="relative group">
                            <div className="absolute -left-[21px] top-2.5 w-3 h-3 rounded-full bg-[#0c101d] border-2 border-emerald-400 group-hover:scale-125 transition-all"></div>
                            <div className="glass-card p-4 rounded-xl border border-white/5 space-y-2 hover:border-emerald-500/40 hover:bg-[#131b31]/80 transition-all">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="text-xs font-bold text-white tracking-tight">
                                  {step.title}
                                </span>
                                {getCategoryBadge(step.category)}
                              </div>

                              <p className="text-xs text-slate-300 leading-relaxed font-normal">
                                {step.description}
                              </p>

                              {step.file_path && (
                                <div
                                  onClick={() => onSelectFile && onSelectFile(step.file_path)}
                                  className="inline-flex items-center space-x-1.5 text-[11px] font-mono text-cyan-400 hover:text-cyan-200 cursor-pointer pt-1 hover:underline transition-colors"
                                  title="View file in File Explorer"
                                >
                                  <FileText className="w-3.5 h-3.5 flex-shrink-0" />
                                  <span className="truncate">{step.file_path}</span>
                                  <ExternalLink className="w-3 h-3 flex-shrink-0 text-slate-500 ml-1" />
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Right Column: Entrypoints, APIs, Gotchas, and Multi-Day Action Checklist */}
            <div className="space-y-6">
              {/* Must-Read Core Entrypoints */}
              <div className="glass-panel p-5 rounded-2xl border border-white/10 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center space-x-1.5">
                    <FileCode className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Must-Read Core Files ({entrypoints.length})</span>
                  </h4>
                </div>

                {entrypoints.length === 0 ? (
                  <div className="p-4 text-xs text-slate-400 text-center">
                    No primary entrypoints identified.
                  </div>
                ) : (
                  <div className="space-y-2 max-h-56 overflow-y-auto pr-1 scrollbar-thin">
                    {entrypoints.map((ep, idx) => {
                      const ext = ep.path.split('.').pop()?.toUpperCase() || 'FILE';
                      let extColor = 'bg-slate-800 text-slate-400';
                      if (['JS', 'JSX'].includes(ext)) extColor = 'bg-amber-500/15 text-amber-300 border-amber-500/20';
                      else if (['TS', 'TSX'].includes(ext)) extColor = 'bg-blue-500/15 text-blue-300 border-blue-500/20';

                      return (
                        <div
                          key={idx}
                          onClick={() => onSelectFile && onSelectFile(ep.path)}
                          className="p-2.5 rounded-xl bg-slate-900/60 border border-white/5 hover:border-cyan-500/40 hover:bg-slate-900 cursor-pointer transition-all flex items-center justify-between group"
                        >
                          <div className="truncate min-w-0 mr-2">
                            <div className="text-xs font-mono font-semibold text-slate-200 group-hover:text-cyan-300 truncate">
                              {ep.label || ep.path.split('/').pop()}
                            </div>
                            <div className="text-[10px] font-mono text-slate-400 truncate">
                              {ep.path}
                            </div>
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

              {/* Critical APIs to Know */}
              {importantApis.length > 0 && (
                <div className="glass-panel p-5 rounded-2xl border border-white/10 space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center space-x-1.5">
                    <Server className="w-3.5 h-3.5 text-amber-400" />
                    <span>Important APIs ({importantApis.length})</span>
                  </h4>
                  <div className="space-y-1.5 max-h-52 overflow-y-auto pr-1 scrollbar-thin">
                    {importantApis.map((apiItem, idx) => {
                      const method = (apiItem.method || 'GET').toUpperCase();
                      let mColor = 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30';
                      if (method === 'POST') mColor = 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
                      else if (method === 'DELETE') mColor = 'bg-rose-500/15 text-rose-300 border-rose-500/30';

                      return (
                        <div
                          key={idx}
                          onClick={() => apiItem.file && onSelectFile && onSelectFile(apiItem.file)}
                          className="p-2 rounded-xl bg-slate-900/60 border border-white/5 hover:border-amber-500/30 cursor-pointer transition-all flex items-center justify-between"
                        >
                          <div className="flex items-center space-x-2 truncate">
                            <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${mColor}`}>
                              {method}
                            </span>
                            <span className="text-xs font-mono font-semibold text-slate-200 truncate">
                              {apiItem.path}
                            </span>
                          </div>
                          {apiItem.file && (
                            <span className="text-[10px] font-mono text-slate-400 truncate max-w-[120px] ml-2">
                              {apiItem.file.split('/').pop()}
                              {apiItem.line && `:${apiItem.line}`}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* High-Risk Components & Blast Radius Rules */}
              <div className="glass-panel p-5 rounded-2xl border border-white/10 space-y-3">
                <div className="flex items-center space-x-2">
                  <Flame className="w-4 h-4 text-rose-400" />
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                    High-Impact Components &amp; Gotchas
                  </h4>
                </div>

                {/* High risk items */}
                {highRiskComponents.length > 0 && (
                  <div className="space-y-1.5 pb-2 border-b border-white/5">
                    {highRiskComponents.slice(0, 4).map((hr, idx) => (
                      <div
                        key={idx}
                        onClick={() => hr.path && onSelectFile && onSelectFile(hr.path)}
                        className="p-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs flex items-center justify-between cursor-pointer hover:bg-rose-500/15 transition-all"
                      >
                        <div className="truncate mr-2">
                          <span className="font-mono font-bold text-rose-200">{hr.label}</span>
                          <span className="text-[10px] font-mono text-slate-400 ml-1.5 truncate">
                            ({hr.path})
                          </span>
                        </div>
                        <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 flex-shrink-0">
                          {hr.affected_files_count} affected
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Gotchas list */}
                <div className="space-y-2 text-xs text-slate-300">
                  {gotchas.map((gotcha, idx) => (
                    <div
                      key={idx}
                      className="p-2 rounded-lg bg-amber-500/5 border border-amber-500/15 flex items-start space-x-2"
                    >
                      <span className="text-amber-400 font-bold">•</span>
                      <span className="leading-snug">{gotcha}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Interactive Ramp-Up Action Checklist */}
              <div className="glass-panel p-5 rounded-2xl border border-white/10 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <CheckCircle className="w-4 h-4 text-emerald-400" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                      Ramp-Up Action Checklist
                    </h4>
                  </div>

                  {completedTotalCount > 0 && (
                    <button
                      onClick={handleResetProgress}
                      className="text-[10px] text-slate-400 hover:text-slate-200 flex items-center space-x-1"
                      title="Reset onboarding task progress"
                    >
                      <RotateCcw className="w-3 h-3" />
                      <span>Reset</span>
                    </button>
                  )}
                </div>

                {/* Overall Progress Bar */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="text-slate-400">Total Completion</span>
                    <span className="text-emerald-300 font-bold">
                      {completedTotalCount} / {totalTasksCount} ({overallPercentage}%)
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-emerald-500 to-cyan-400 rounded-full transition-all duration-300"
                      style={{ width: `${overallPercentage}%` }}
                    ></div>
                  </div>
                </div>

                {/* Day Switcher Tabs */}
                <div className="flex items-center space-x-1.5 border-b border-white/5 pb-2">
                  {[1, 2, 3].map((d) => {
                    const isTabActive = activeChecklistDay === d;
                    const dayTasks = multiDayTasks[d] || [];
                    const dayDone = dayTasks.every((_, idx) => completedTasks[`day-${d}-task-${idx}`]);

                    return (
                      <button
                        key={d}
                        onClick={() => setActiveChecklistDay(d)}
                        className={`flex-1 py-1.5 rounded-lg text-xs font-mono font-bold transition-all flex items-center justify-center space-x-1 ${
                          isTabActive
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                            : 'bg-white/5 text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {dayDone && <CheckCircle className="w-3 h-3 text-emerald-400" />}
                        <span>Day {d}</span>
                      </button>
                    );
                  })}
                </div>

                {/* Active Day Task Items */}
                <div className="space-y-2">
                  {currentDayTasks.map((task, idx) => {
                    const taskKey = `day-${activeChecklistDay}-task-${idx}`;
                    const isDone = completedTasks[taskKey];

                    return (
                      <div
                        key={idx}
                        onClick={() => toggleTask(taskKey)}
                        className={`p-3 rounded-xl border cursor-pointer transition-all flex items-start space-x-2.5 ${
                          isDone
                            ? 'bg-emerald-500/10 border-emerald-500/30 text-slate-400 line-through'
                            : 'bg-slate-900/60 border-white/5 hover:border-emerald-500/30 text-slate-200'
                        }`}
                      >
                        {isDone ? (
                          <CheckSquare className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                        ) : (
                          <Square className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
                        )}
                        <span className="text-xs leading-relaxed">{task}</span>
                      </div>
                    );
                  })}
                </div>

                {/* Milestone Celebration Banner */}
                {isCurrentDayFullyCompleted && (
                  <div className="p-3.5 rounded-xl bg-gradient-to-r from-emerald-500/20 to-cyan-500/15 border border-emerald-500/30 text-xs space-y-2 animate-in fade-in duration-300">
                    <div className="flex items-center space-x-2 text-emerald-300 font-bold">
                      <Sparkles className="w-4 h-4" />
                      <span>
                        {activeChecklistDay === 3
                          ? '🎉 Full Codebase Ramp-Up Complete!'
                          : `🎉 Day ${activeChecklistDay} Milestones Completed!`}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-300 leading-snug">
                      {activeChecklistDay === 1
                        ? 'You have inspected core bootstrappers and entry routes. You are now officially Day-1 Ready.'
                        : activeChecklistDay === 2
                        ? 'Data contracts, controller handlers, and model constraints verified. Ready for reliability checks.'
                        : 'Congratulations! You have mastered the architecture, gotchas, and test suite of this repository.'}
                    </p>
                    {activeChecklistDay < 3 && (
                      <button
                        onClick={() => setActiveChecklistDay((prev) => prev + 1)}
                        className="mt-1 w-full py-1.5 rounded-lg bg-emerald-500/30 hover:bg-emerald-500/40 text-emerald-200 font-semibold text-xs transition-all flex items-center justify-center space-x-1"
                      >
                        <span>Advance to Day {activeChecklistDay + 1} Tasks</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="glass-panel p-16 rounded-2xl border border-white/10 text-center space-y-3">
          <GraduationCap className="w-8 h-8 text-slate-500 mx-auto" />
          <h3 className="text-base font-bold text-white">No Role Guide Selected</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            Select a developer persona from the tabs above to view its curated onboarding curriculum.
          </p>
        </div>
      )}
    </div>
  );
};
