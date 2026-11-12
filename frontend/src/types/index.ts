export type NodeType =
  | 'file'
  | 'function'
  | 'class'
  | 'module'
  | 'endpoint'
  | 'api'
  | 'directory'
  | 'repository'
  | 'externaldependency'
  | string;

export interface GraphNode {
  id: string;
  label: string;
  type: NodeType;
  path?: string;
  file_path?: string;
  line_number?: number;
  line?: number;
  exported?: boolean;
  docstring?: string;
  calls_count?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface ApiEndpoint {
  method: string;
  path: string;
  handler?: string;
  file?: string;
  line?: number;
  description?: string;
}

export interface ArchitectureLayer {
  name: string;
  files: number;
}

export interface ComponentMeta {
  name: string;
  responsibility: string;
  files: number;
  lines: number;
  languages?: string[];
}

export interface SummaryInfo {
  purpose?: string;
  architecture_style?: string;
  headline?: string;
  tech_stack?: string[];
  key_directories?: string[];
  entry_points?: string[];
  primary_components?: string[];
  external_dependencies?: string[];
  architecture_layers?: ArchitectureLayer[];
  quality_notes?: string[];
  stats?: {
    files?: number;
    functions?: number;
    classes?: number;
    imports?: number;
    apis?: number;
    lines?: number;
    total_files?: number;
    total_functions?: number;
    total_classes?: number;
    total_apis?: number;
    [key: string]: any;
  };
}

export interface AnalysisData {
  repository?: {
    name: string;
    path: string;
  };
  summary: SummaryInfo;
  components?: ComponentMeta[];
  nodes: GraphNode[];
  relationships: GraphEdge[];
  files: Array<{
    path: string;
    functions?: string[];
    classes?: string[];
    imports?: string[];
    [key: string]: any;
  }>;
  apis?: ApiEndpoint[];
  active_repo_id?: string;
  impact_index?: Record<string, any>;
}

export interface RepositoryItem {
  id: string;
  name: string;
  root_path: string;
  source: 'local' | 'github';
  headline?: string;
  stats?: Record<string, any>;
}

export interface RepositoryListResponse {
  active_repo_id: string;
  repositories: RepositoryItem[];
}

export interface DependentNode {
  id: string;
  name: string;
  kind: string;
  file: string;
  start_line?: number;
  relation: string;
}

export interface ImpactResponse {
  target: GraphNode;
  risk: 'Low' | 'Medium' | 'High';
  blast_score: number;
  affected_files: string[];
  affected_apis: string[];
  affected_tests: string[];
  direct_dependents: DependentNode[];
  transitive_dependents: DependentNode[];
  recommendations: string[];
  error?: string;
}

export interface FlowStep {
  step_number?: number;
  order?: number;
  node_id?: string;
  label?: string;
  symbol?: string;
  type?: string;
  role?: string;
  path?: string;
  file?: string;
  line?: number | null;
  relationship_type?: string;
  action?: string;
  description?: string;
  caller_node_id?: string | null;
}

export interface FeatureFlow {
  flow_id?: string;
  id?: string;
  name: string;
  category?: string;
  description?: string;
  trigger?: string;
  entry_point?: FlowStep;
  steps: FlowStep[];
  involved_files?: string[];
  files?: string[];
  mermaid_sequence?: string;
  mermaid_flowchart?: string;
  mermaid?: string;
}

export interface ReadingStep {
  day: number;
  title: string;
  description: string;
  file_path: string;
  line_start?: number | null;
  line_end?: number | null;
  entity_id?: string | null;
  category?: string;
}

export interface KeyEntrypoint {
  path: string;
  label?: string;
  importance?: string;
  rationale?: string;
}

export interface ImportantApi {
  id?: string;
  method: string;
  path: string;
  file?: string;
  line?: number;
}

export interface HighRiskComponent {
  id: string;
  label: string;
  path: string;
  risk: string;
  affected_files_count: number;
}

export interface RoleLearningPhase {
  phase: string;
  title: string;
  description: string;
  files: string[];
}

export interface RoleGuide {
  role: string;
  title?: string;
  mission?: string;
  summary: string;
  reading_path?: ReadingStep[];
  key_entrypoints?: KeyEntrypoint[];
  important_apis?: ImportantApi[];
  key_test_suites?: string[];
  high_risk_components?: HighRiskComponent[];
  learning_path?: RoleLearningPhase[];
  core_files?: Array<{
    path: string;
    importance?: string;
    rationale?: string;
  }>;
  gotchas?: string[];
  first_tasks?: string[];
}

export interface FileContentResponse {
  path: string;
  content: string;
  lines: number;
  error?: string;
}

export interface ChatSource {
  file: string;
  score?: number;
  title?: string;
  line?: number;
}

export interface ChatResponse {
  answer: string;
  conversation_id: string;
  turn: number;
  sources: ChatSource[];
  error?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  citations?: ChatSource[];
}

export interface AiStatus {
  configured: boolean;
  provider: string | null;
  model: string | null;
  mode?: string;
  error?: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'user';
  created_at?: string;
}

export interface AuthResponse {
  status: string;
  token?: string;
  user?: User;
  error?: string;
}
