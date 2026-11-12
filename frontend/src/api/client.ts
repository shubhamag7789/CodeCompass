import type {
  AiStatus,
  AnalysisData,
  AuthResponse,
  ChatResponse,
  FeatureFlow,
  FileContentResponse,
  ImpactResponse,
  RepositoryListResponse,
  RoleGuide,
  User,
} from '../types';

const API_BASE = '/api';
const TOKEN_KEY = 'codecompass_token';

export const authStorage = {
  getToken(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  setToken(token: string): void {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {}
  },
  clearToken(): void {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {}
  },
};

function getHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
  const token = authStorage.getToken();
  const headers: Record<string, string> = { ...extraHeaders };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(errorData.error || `HTTP ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  // Authentication & User Profile
  async login(payload: { email: string; password: string }): Promise<AuthResponse> {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await handleResponse<AuthResponse>(res);
    if (data.token) {
      authStorage.setToken(data.token);
    }
    return data;
  },

  async register(payload: {
    email: string;
    password: string;
    name: string;
    security_question?: string;
    security_answer?: string;
    recovery_passphrase?: string;
  }): Promise<AuthResponse & { security_question?: string; recovery_passphrase?: string }> {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await handleResponse<AuthResponse & { security_question?: string; recovery_passphrase?: string }>(res);
    if (data.token) {
      authStorage.setToken(data.token);
    }
    return data;
  },

  async logout(): Promise<void> {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: getHeaders({ 'Content-Type': 'application/json' }),
      });
    } finally {
      authStorage.clearToken();
    }
  },

  async requestPasswordReset(email: string): Promise<{
    status: string;
    email: string;
    security_question?: string;
    has_security_question?: boolean;
    has_recovery_passphrase?: boolean;
    code?: string;
    message?: string;
  }> {
    const res = await fetch(`${API_BASE}/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    return handleResponse(res);
  },

  async resetPassword(payload: {
    email: string;
    new_password: string;
    code?: string;
    security_answer?: string;
    recovery_passphrase?: string;
    security_question?: string;
  }): Promise<AuthResponse> {
    const res = await fetch(`${API_BASE}/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await handleResponse<AuthResponse>(res);
    if (data.token) {
      authStorage.setToken(data.token);
    }
    return data;
  },

  async getSecuritySettings(): Promise<{
    status: string;
    security_question: string;
    has_security_question: boolean;
    has_recovery_passphrase: boolean;
  }> {
    const res = await fetch(`${API_BASE}/auth/security-settings`, {
      headers: getHeaders(),
    });
    return handleResponse(res);
  },

  async updateSecuritySettings(payload: {
    security_question: string;
    security_answer: string;
    recovery_passphrase?: string;
  }): Promise<{ status: string; message: string; security_question: string }> {
    const res = await fetch(`${API_BASE}/auth/security-settings`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async getCurrentUser(): Promise<User | null> {
    const token = authStorage.getToken();
    if (!token) return null;
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: getHeaders(),
      });
      if (res.status === 401) {
        authStorage.clearToken();
        return null;
      }
      const data = await handleResponse<{ user: User }>(res);
      return data.user || null;
    } catch {
      return null;
    }
  },

  // Codebase Intelligence
  async getAiStatus(): Promise<AiStatus> {
    const res = await fetch(`${API_BASE}/ai/status`, {
      headers: getHeaders(),
    });
    return handleResponse<AiStatus>(res);
  },

  async getRepositories(): Promise<RepositoryListResponse> {
    const res = await fetch(`${API_BASE}/repositories`, {
      headers: getHeaders(),
    });
    return handleResponse<RepositoryListResponse>(res);
  },

  async switchRepository(repoId: string): Promise<{ status: string; active_repo_id: string }> {
    const res = await fetch(`${API_BASE}/switch-repo`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ repo_id: repoId }),
    });
    return handleResponse(res);
  },

  async deleteRepository(repoId: string): Promise<{ status: string; active_repo_id: string; repositories: any[] }> {
    const res = await fetch(`${API_BASE}/repositories/delete`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ repo_id: repoId }),
    });
    return handleResponse(res);
  },

  async analyzeRepository(pathOrUrl: string): Promise<AnalysisData> {
    const res = await fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ path: pathOrUrl }),
    });
    return handleResponse<AnalysisData>(res);
  },

  async getAnalysis(repoId?: string): Promise<AnalysisData> {
    const url = repoId ? `${API_BASE}/analysis?repo=${encodeURIComponent(repoId)}` : `${API_BASE}/analysis`;
    const res = await fetch(url, { headers: getHeaders() });
    return handleResponse<AnalysisData>(res);
  },

  async getFileTree(repoId?: string): Promise<{ files: string[] }> {
    const url = repoId ? `${API_BASE}/filetree?repo=${encodeURIComponent(repoId)}` : `${API_BASE}/filetree`;
    const res = await fetch(url, { headers: getHeaders() });
    return handleResponse<{ files: string[] }>(res);
  },

  async getFileContent(filePath: string, repoId?: string): Promise<FileContentResponse> {
    const params = new URLSearchParams({ path: filePath });
    if (repoId) params.append('repo', repoId);
    const res = await fetch(`${API_BASE}/file?${params.toString()}`, { headers: getHeaders() });
    return handleResponse<FileContentResponse>(res);
  },

  async getImpact(nodeId: string, repoId?: string): Promise<ImpactResponse> {
    const params = new URLSearchParams({ id: nodeId });
    if (repoId) params.append('repo', repoId);
    const res = await fetch(`${API_BASE}/impact?${params.toString()}`, { headers: getHeaders() });
    return handleResponse<ImpactResponse>(res);
  },

  async getFlows(repoId?: string): Promise<{ flows: any[] }> {
    const url = repoId ? `${API_BASE}/flow/discover?repo=${encodeURIComponent(repoId)}` : `${API_BASE}/flow/discover`;
    const res = await fetch(url, { headers: getHeaders() });
    return handleResponse<{ flows: any[] }>(res);
  },

  async traceFlow(entryId?: string, query?: string, repoId?: string): Promise<FeatureFlow> {
    const params = new URLSearchParams();
    if (entryId) params.append('id', entryId);
    if (query) params.append('query', query);
    if (repoId) params.append('repo', repoId);
    const res = await fetch(`${API_BASE}/flow/trace?${params.toString()}`, { headers: getHeaders() });
    return handleResponse<FeatureFlow>(res);
  },

  async getOnboardingGuides(repoId?: string): Promise<{ roles: Record<string, RoleGuide> }> {
    const url = repoId ? `${API_BASE}/onboarding?repo=${encodeURIComponent(repoId)}` : `${API_BASE}/onboarding`;
    const res = await fetch(url, { headers: getHeaders() });
    return handleResponse<{ roles: Record<string, RoleGuide> }>(res);
  },

  async getRoleGuide(role: string, repoId?: string): Promise<RoleGuide> {
    const params = new URLSearchParams({ role });
    if (repoId) params.append('repo', repoId);
    const res = await fetch(`${API_BASE}/onboarding?${params.toString()}`, { headers: getHeaders() });
    return handleResponse<RoleGuide>(res);
  },

  async sendChatMessage(payload: {
    question: string;
    conversation_id?: string;
    repo_id?: string;
    reset?: boolean;
  }): Promise<ChatResponse> {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });
    return handleResponse<ChatResponse>(res);
  },
};
