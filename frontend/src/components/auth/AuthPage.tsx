import React, { useState } from 'react';
import {
  Compass,
  Mail,
  Lock,
  User as UserIcon,
  Eye,
  EyeOff,
  ArrowRight,
  ShieldCheck,
  Sparkles,
  GitBranch,
  Layers,
  AlertCircle,
  Loader2,
  CheckCircle2,
  KeyRound,
  ArrowLeft,
  Copy,
  RefreshCw,
  HelpCircle,
} from 'lucide-react';
import { api } from '../../api/client';
import type { User } from '../../types';

interface AuthPageProps {
  onAuthSuccess: (user: User) => void;
}

const DEFAULT_SECURITY_QUESTIONS = [
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

export const AuthPage: React.FC<AuthPageProps> = ({ onAuthSuccess }) => {
  const [mode, setMode] = useState<'signin' | 'signup' | 'forgot'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Security Question & Passphrase state for Registration
  const [selectedQuestion, setSelectedQuestion] = useState(DEFAULT_SECURITY_QUESTIONS[0]);
  const [customQuestion, setCustomQuestion] = useState('');
  const [securityAnswer, setSecurityAnswer] = useState('');
  const [recoveryPassphrase, setRecoveryPassphrase] = useState<string>(() => generatePassphrase());
  const [isCopied, setIsCopied] = useState(false);

  // Forgot password flow state
  const [forgotStep, setForgotStep] = useState<1 | 2>(1);
  const [recoveryInfo, setRecoveryInfo] = useState<{
    security_question?: string;
    has_security_question?: boolean;
    has_recovery_passphrase?: boolean;
  } | null>(null);
  const [recoveryMethod, setRecoveryMethod] = useState<'question' | 'passphrase'>('question');
  const [securityAnswerInput, setSecurityAnswerInput] = useState('');
  const [recoveryPassphraseInput, setRecoveryPassphraseInput] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const handleCopyPassphrase = () => {
    navigator.clipboard.writeText(recoveryPassphrase);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const handleRegeneratePassphrase = () => {
    setRecoveryPassphrase(generatePassphrase());
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (!email || !email.includes('@')) {
      setError('Please provide a valid email address.');
      return;
    }

    // Forgot password flow
    if (mode === 'forgot') {
      if (forgotStep === 1) {
        setIsLoading(true);
        try {
          const res = await api.requestPasswordReset(email);
          setRecoveryInfo(res);
          setForgotStep(2);
          setSecurityAnswerInput('');
          setRecoveryPassphraseInput('');
          setNewPassword('');
          setConfirmPassword('');
          if (!res.has_security_question && !res.has_recovery_passphrase) {
            setSuccessMessage('Account located. Set up your recovery question and new password below.');
          } else {
            setSuccessMessage('Account verified. Answer your security question or enter your recovery passphrase.');
          }
        } catch (err: any) {
          setError(err.message || 'No account found with this email address.');
        } finally {
          setIsLoading(false);
        }
      } else {
        // Step 2: verify recovery method and reset password
        if (newPassword.length < 6) {
          setError('New password must be at least 6 characters long.');
          return;
        }
        if (newPassword !== confirmPassword) {
          setError('Passwords do not match. Please verify your new password.');
          return;
        }

        const isLegacySetup = !recoveryInfo?.has_security_question && !recoveryInfo?.has_recovery_passphrase;
        const activeQuestion = selectedQuestion === 'CUSTOM' ? customQuestion : selectedQuestion;

        if (isLegacySetup && (!activeQuestion || !securityAnswerInput.trim())) {
          setError('Please select a security question and provide an answer to secure your account.');
          return;
        }

        if (!isLegacySetup) {
          if (recoveryMethod === 'question' && !securityAnswerInput.trim()) {
            setError('Please provide the answer to your security question.');
            return;
          }
          if (recoveryMethod === 'passphrase' && !recoveryPassphraseInput.trim()) {
            setError('Please enter your 4-word recovery passphrase.');
            return;
          }
        }

        setIsLoading(true);
        try {
          const res = await api.resetPassword({
            email,
            new_password: newPassword,
            security_answer: securityAnswerInput.trim() || undefined,
            recovery_passphrase: recoveryMethod === 'passphrase' ? recoveryPassphraseInput.trim() : undefined,
            security_question: isLegacySetup ? activeQuestion : undefined,
          });

          if (res.user) {
            onAuthSuccess(res.user);
          } else {
            setError(res.error || 'Password reset failed.');
          }
        } catch (err: any) {
          setError(err.message || 'Password reset failed. Please check your answer or passphrase.');
        } finally {
          setIsLoading(false);
        }
      }
      return;
    }

    // Sign in / Sign up validation
    if (password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }

    if (mode === 'signup') {
      if (!name.trim()) {
        setError('Please provide your name.');
        return;
      }
      const activeQuestion = selectedQuestion === 'CUSTOM' ? customQuestion : selectedQuestion;
      if (!activeQuestion.trim()) {
        setError('Please select or specify a security question.');
        return;
      }
      if (!securityAnswer.trim()) {
        setError('Please provide an answer to your security question.');
        return;
      }
    }

    setIsLoading(true);
    try {
      if (mode === 'signin') {
        const res = await api.login({ email, password });
        if (res.user) {
          onAuthSuccess(res.user);
        } else {
          setError(res.error || 'Login failed. Please check your credentials.');
        }
      } else {
        const activeQuestion = selectedQuestion === 'CUSTOM' ? customQuestion : selectedQuestion;
        const res = await api.register({
          email,
          password,
          name,
          security_question: activeQuestion,
          security_answer: securityAnswer,
          recovery_passphrase: recoveryPassphrase,
        });
        if (res.user) {
          onAuthSuccess(res.user);
        } else {
          setError(res.error || 'Registration failed. Try again.');
        }
      }
    } catch (err: any) {
      setError(err.message || 'Authentication error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickDemo = async () => {
    setEmail('developer@codecompass.dev');
    setPassword('Developer@123');
    setError(null);
    setSuccessMessage(null);
    setIsLoading(true);
    try {
      let res;
      try {
        res = await api.login({
          email: 'developer@codecompass.dev',
          password: 'Developer@123',
        });
      } catch {
        res = await api.register({
          email: 'developer@codecompass.dev',
          password: 'Developer@123',
          name: 'Demo Developer',
          security_question: 'What was the name of your first school or college?',
          security_answer: 'Stanford',
          recovery_passphrase: 'galaxy-harbor-matrix-falcon',
        });
      }
      if (res.user) {
        onAuthSuccess(res.user);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to sign in with demo credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#070b14] text-slate-100 flex items-center justify-center p-4 relative overflow-hidden font-sans">
      {/* Background glow effects */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none -translate-x-1/2 -translate-y-1/2"></div>
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl pointer-events-none translate-x-1/2 translate-y-1/2"></div>
      <div className="absolute top-1/2 right-1/3 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>

      <div className="w-full max-w-4xl grid grid-cols-1 lg:grid-cols-12 gap-8 items-center relative z-10 my-8">
        {/* Left Side: Brand Story & Architecture Highlights */}
        <div className="lg:col-span-7 space-y-6 px-2 lg:px-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center text-white shadow-lg shadow-cyan-500/25 ring-1 ring-white/20">
              <Compass className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                CodeCompass
              </h1>
              <p className="text-xs text-cyan-400 font-mono">Codebase Intelligence Platform</p>
            </div>
          </div>

          <div className="space-y-3">
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight leading-tight">
              Enterprise-grade code exploration,{' '}
              <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                isolated per developer.
              </span>
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 leading-relaxed max-w-lg">
              Navigate, understand, and safely modify complex repositories. Your personal analysis,
              dependency graphs, and impact evaluations are strictly isolated to your user account.
            </p>
          </div>

          {/* Pillars */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 hover:border-cyan-500/30 transition-all space-y-2">
              <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                <GitBranch className="w-4 h-4" />
              </div>
              <h3 className="text-xs font-bold text-slate-200">Zero Data Loss</h3>
              <p className="text-[11px] text-slate-400 leading-normal">
                Every scanned repo and search index is saved in your dedicated SQLite partition.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 hover:border-blue-500/30 transition-all space-y-2">
              <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <h3 className="text-xs font-bold text-slate-200">Self-Contained Security</h3>
              <p className="text-[11px] text-slate-400 leading-normal">
                Account recovery via salted PBKDF2 security questions and passphrases. 100% offline-ready.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-6 text-xs text-slate-400 pt-2">
            <div className="flex items-center space-x-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
              <span>PBKDF2 SHA-256 Hashing</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
              <span>Session Bearer Tokens</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
              <span>Role-Based Access</span>
            </div>
          </div>
        </div>

        {/* Right Side: Authentication Card */}
        <div className="lg:col-span-5">
          <div className="p-6 sm:p-8 rounded-2xl bg-[#0e1426]/90 border border-white/10 backdrop-blur-xl shadow-2xl space-y-6">
            {/* Header Tabs */}
            {mode !== 'forgot' ? (
              <div className="flex border-b border-white/10 pb-4">
                <button
                  type="button"
                  onClick={() => {
                    setMode('signin');
                    setError(null);
                    setSuccessMessage(null);
                  }}
                  className={`flex-1 pb-2 text-sm font-semibold transition-all relative ${
                    mode === 'signin'
                      ? 'text-cyan-400 border-b-2 border-cyan-400'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Sign In
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setMode('signup');
                    setError(null);
                    setSuccessMessage(null);
                  }}
                  className={`flex-1 pb-2 text-sm font-semibold transition-all relative ${
                    mode === 'signup'
                      ? 'text-cyan-400 border-b-2 border-cyan-400'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Create Account
                </button>
              </div>
            ) : (
              <div className="border-b border-white/10 pb-4 flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <KeyRound className="w-4 h-4 text-cyan-400" />
                  <span className="text-sm font-bold text-white">
                    {forgotStep === 1 ? 'Find Account' : 'Account Recovery'}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setMode('signin');
                    setForgotStep(1);
                    setError(null);
                    setSuccessMessage(null);
                  }}
                  className="text-xs text-slate-400 hover:text-cyan-300 transition-colors flex items-center space-x-1"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Back to Sign In</span>
                </button>
              </div>
            )}

            {/* Error Banner */}
            {error && (
              <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-start space-x-2 animate-in fade-in">
                <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                <span className="leading-snug">{error}</span>
              </div>
            )}

            {/* Success Banner */}
            {successMessage && (
              <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-start space-x-2 animate-in fade-in">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                <span className="leading-snug">{successMessage}</span>
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === 'signup' && (
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider">
                    Full Name
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                      <UserIcon className="w-4 h-4" />
                    </div>
                    <input
                      type="text"
                      required
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="e.g. Shubham Agarwal"
                      className="w-full pl-10 pr-4 py-2 bg-black/40 border border-white/10 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                    />
                  </div>
                </div>
              )}

              {/* Email field */}
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider">
                  Email Address
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <Mail className="w-4 h-4" />
                  </div>
                  <input
                    type="email"
                    required
                    disabled={mode === 'forgot' && forgotStep === 2}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="shubhamagarwal47910@gmail.com"
                    className="w-full pl-10 pr-4 py-2 bg-black/40 border border-white/10 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all disabled:opacity-60"
                  />
                </div>
              </div>

              {/* Password field for signin / signup */}
              {mode !== 'forgot' && (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider">
                      Password
                    </label>
                    {mode === 'signin' ? (
                      <button
                        type="button"
                        onClick={() => {
                          setMode('forgot');
                          setForgotStep(1);
                          setError(null);
                          setSuccessMessage(null);
                        }}
                        className="text-[11px] text-cyan-400 hover:text-cyan-300 transition-colors font-medium hover:underline"
                      >
                        Forgot password?
                      </button>
                    ) : (
                      <span className="text-[10px] text-slate-500">Min 6 characters</span>
                    )}
                  </div>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                      <Lock className="w-4 h-4" />
                    </div>
                    <input
                      type={showPassword ? 'text' : 'password'}
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      className="w-full pl-10 pr-10 py-2 bg-black/40 border border-white/10 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-200 transition-colors"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              )}

              {/* Sign Up: Security Question & Recovery Passphrase */}
              {mode === 'signup' && (
                <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/10 space-y-3">
                  <div className="flex items-center space-x-2 text-cyan-300">
                    <ShieldCheck className="w-4 h-4" />
                    <span className="text-xs font-bold uppercase tracking-wider">
                      Account Recovery Protection
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 leading-tight">
                    Recover your account anytime without needing an external email server or SMTP credentials.
                  </p>

                  {/* Security Question selection */}
                  <div className="space-y-1">
                    <label className="text-[10px] font-semibold text-slate-300">
                      Security Question
                    </label>
                    <select
                      value={selectedQuestion}
                      onChange={(e) => setSelectedQuestion(e.target.value)}
                      className="w-full px-3 py-1.5 bg-[#0a0f1d] border border-white/10 rounded-lg text-xs text-white focus:outline-none focus:border-cyan-500"
                    >
                      {DEFAULT_SECURITY_QUESTIONS.map((q) => (
                        <option key={q} value={q} className="bg-[#0a0f1d] text-white">
                          {q}
                        </option>
                      ))}
                      <option value="CUSTOM" className="bg-[#0a0f1d] text-cyan-300">
                        + Write a custom question...
                      </option>
                    </select>

                    {selectedQuestion === 'CUSTOM' && (
                      <input
                        type="text"
                        required
                        value={customQuestion}
                        onChange={(e) => setCustomQuestion(e.target.value)}
                        placeholder="Enter your custom security question"
                        className="w-full mt-1.5 px-3 py-1.5 bg-black/40 border border-white/10 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                      />
                    )}
                  </div>

                  {/* Security Answer */}
                  <div className="space-y-1">
                    <label className="text-[10px] font-semibold text-slate-300">
                      Security Answer (case-insensitive)
                    </label>
                    <input
                      type="text"
                      required
                      value={securityAnswer}
                      onChange={(e) => setSecurityAnswer(e.target.value)}
                      placeholder="e.g. Lincoln High School"
                      className="w-full px-3 py-1.5 bg-black/40 border border-white/10 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                    />
                  </div>

                  {/* Auto-generated Recovery Passphrase */}
                  <div className="space-y-1 pt-1 border-t border-white/5">
                    <div className="flex items-center justify-between text-[10px] text-slate-300">
                      <span className="font-semibold">Recovery Passphrase (Secret Key)</span>
                      <button
                        type="button"
                        onClick={handleRegeneratePassphrase}
                        className="text-slate-400 hover:text-cyan-300 transition-colors flex items-center space-x-1"
                        title="Generate new words"
                      >
                        <RefreshCw className="w-3 h-3" />
                        <span>Regenerate</span>
                      </button>
                    </div>

                    <div className="flex items-center space-x-2">
                      <div className="flex-1 font-mono text-xs px-2.5 py-1.5 rounded-lg bg-black/60 border border-cyan-500/20 text-cyan-300 tracking-wider select-all truncate">
                        {recoveryPassphrase}
                      </div>
                      <button
                        type="button"
                        onClick={handleCopyPassphrase}
                        className="px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-slate-200 transition-colors flex items-center space-x-1"
                      >
                        {isCopied ? (
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
                </div>
              )}

              {/* Forgot password Step 2: Answer Question OR Passphrase + Set New Password */}
              {mode === 'forgot' && forgotStep === 2 && (
                <div className="space-y-4">
                  {/* If user already had security recovery configured */}
                  {recoveryInfo?.has_security_question || recoveryInfo?.has_recovery_passphrase ? (
                    <div className="space-y-3">
                      {/* Method Toggle */}
                      {recoveryInfo.has_security_question && recoveryInfo.has_recovery_passphrase && (
                        <div className="flex rounded-lg bg-black/40 p-1 border border-white/10 text-xs">
                          <button
                            type="button"
                            onClick={() => setRecoveryMethod('question')}
                            className={`flex-1 py-1 rounded-md transition-all font-medium flex items-center justify-center space-x-1.5 ${
                              recoveryMethod === 'question'
                                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                                : 'text-slate-400 hover:text-white'
                            }`}
                          >
                            <HelpCircle className="w-3.5 h-3.5" />
                            <span>Security Question</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => setRecoveryMethod('passphrase')}
                            className={`flex-1 py-1 rounded-md transition-all font-medium flex items-center justify-center space-x-1.5 ${
                              recoveryMethod === 'passphrase'
                                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                                : 'text-slate-400 hover:text-white'
                            }`}
                          >
                            <ShieldCheck className="w-3.5 h-3.5" />
                            <span>Recovery Passphrase</span>
                          </button>
                        </div>
                      )}

                      {recoveryMethod === 'question' && recoveryInfo.security_question && (
                        <div className="space-y-1.5">
                          <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-200 text-xs">
                            <span className="text-[10px] uppercase font-bold text-cyan-400 block mb-0.5">
                              Security Question:
                            </span>
                            <span className="font-semibold text-white">
                              {recoveryInfo.security_question}
                            </span>
                          </div>
                          <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider block pt-1">
                            Your Security Answer
                          </label>
                          <input
                            type="text"
                            required
                            value={securityAnswerInput}
                            onChange={(e) => setSecurityAnswerInput(e.target.value)}
                            placeholder="Enter your security answer"
                            className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                          />
                        </div>
                      )}

                      {recoveryMethod === 'passphrase' && (
                        <div className="space-y-1.5">
                          <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider block">
                            4-Word Recovery Passphrase
                          </label>
                          <input
                            type="text"
                            required
                            value={recoveryPassphraseInput}
                            onChange={(e) => setRecoveryPassphraseInput(e.target.value)}
                            placeholder="e.g. galaxy-harbor-matrix-falcon"
                            className="w-full px-3.5 py-2 bg-black/40 border border-white/10 rounded-xl text-xs text-cyan-300 font-mono placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                          />
                        </div>
                      )}
                    </div>
                  ) : (
                    /* Legacy user without security question set: allow immediate setup & reset */
                    <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 space-y-3">
                      <div className="flex items-center space-x-2 text-amber-300 text-xs font-bold">
                        <KeyRound className="w-4 h-4" />
                        <span>Account Setup & Verification</span>
                      </div>
                      <p className="text-[11px] text-amber-200/80 leading-relaxed">
                        Choose your security question and answer to verify and permanently secure your account.
                      </p>

                      <div className="space-y-1">
                        <label className="text-[10px] font-semibold text-slate-300">
                          Security Question
                        </label>
                        <select
                          value={selectedQuestion}
                          onChange={(e) => setSelectedQuestion(e.target.value)}
                          className="w-full px-3 py-1.5 bg-[#0a0f1d] border border-white/10 rounded-lg text-xs text-white focus:outline-none focus:border-cyan-500"
                        >
                          {DEFAULT_SECURITY_QUESTIONS.map((q) => (
                            <option key={q} value={q} className="bg-[#0a0f1d] text-white">
                              {q}
                            </option>
                          ))}
                          <option value="CUSTOM" className="bg-[#0a0f1d] text-cyan-300">
                            + Write a custom question...
                          </option>
                        </select>
                      </div>

                      <div className="space-y-1">
                        <label className="text-[10px] font-semibold text-slate-300">
                          Your Answer
                        </label>
                        <input
                          type="text"
                          required
                          value={securityAnswerInput}
                          onChange={(e) => setSecurityAnswerInput(e.target.value)}
                          placeholder="Enter your security answer"
                          className="w-full px-3 py-1.5 bg-black/40 border border-white/10 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                        />
                      </div>
                    </div>
                  )}

                  {/* New Password & Confirm Password */}
                  <div className="space-y-3 pt-2 border-t border-white/10">
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider">
                          New Password
                        </label>
                        <span className="text-[10px] text-slate-500">Min 6 characters</span>
                      </div>
                      <div className="relative">
                        <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                          <Lock className="w-4 h-4" />
                        </div>
                        <input
                          type={showPassword ? 'text' : 'password'}
                          required
                          value={newPassword}
                          onChange={(e) => setNewPassword(e.target.value)}
                          placeholder="••••••••"
                          className="w-full pl-10 pr-10 py-2 bg-black/40 border border-white/10 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-200 transition-colors"
                        >
                          {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider">
                        Confirm New Password
                      </label>
                      <div className="relative">
                        <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                          <Lock className="w-4 h-4" />
                        </div>
                        <input
                          type={showPassword ? 'text' : 'password'}
                          required
                          value={confirmPassword}
                          onChange={(e) => setConfirmPassword(e.target.value)}
                          placeholder="••••••••"
                          className="w-full pl-10 pr-4 py-2 bg-black/40 border border-white/10 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="w-full mt-2 py-3 px-4 rounded-xl bg-gradient-to-r from-blue-600 via-cyan-500 to-cyan-400 hover:from-blue-500 hover:to-cyan-300 text-white font-semibold text-xs shadow-lg shadow-cyan-500/20 active:scale-[0.98] transition-all flex items-center justify-center space-x-2 disabled:opacity-50"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Processing...</span>
                  </>
                ) : mode === 'forgot' ? (
                  forgotStep === 1 ? (
                    <>
                      <span>Find Account & Recover</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  ) : (
                    <>
                      <span>Reset Password & Sign In</span>
                      <CheckCircle2 className="w-4 h-4" />
                    </>
                  )
                ) : (
                  <>
                    <span>{mode === 'signin' ? 'Sign In to Workspace' : 'Create Account & Start'}</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>

            {mode !== 'forgot' && (
              <>
                <div className="relative flex py-1 items-center">
                  <div className="flex-grow border-t border-white/10"></div>
                  <span className="flex-shrink mx-3 text-[10px] text-slate-500 uppercase tracking-widest font-mono">
                    or
                  </span>
                  <div className="flex-grow border-t border-white/10"></div>
                </div>

                {/* Quick Demo Button */}
                <button
                  type="button"
                  onClick={handleQuickDemo}
                  disabled={isLoading}
                  className="w-full py-2.5 px-4 rounded-xl bg-white/[0.05] hover:bg-white/[0.09] border border-white/10 text-slate-300 hover:text-white font-medium text-xs transition-all flex items-center justify-center space-x-2"
                >
                  <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Instant Demo Access (1-Click)</span>
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
