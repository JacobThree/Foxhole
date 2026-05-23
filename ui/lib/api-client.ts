export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, statusText: string, detail: unknown) {
    super(`API Error: ${status} ${statusText}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    throw new ApiError(response.status, response.statusText, detail);
  }

  return response.json();
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export interface ToolResult {
  success: boolean;
  data: unknown;
  error: string | null;
  duration_ms: number;
  output_mode: string;
  raw_data_withheld: boolean;
  raw_line_count: number | null;
  raw_bytes: number | null;
  write_action: {
    requested: boolean;
    safety: string;
    confirmation_required: boolean;
    confirmation_token: string | null;
    audit_id: string | null;
  };
}

export interface ToolTrace {
  tool_call_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  result: ToolResult;
}

export interface DiagnosticFinding {
  title: string;
  summary: string;
  risk: string;
  confidence: string;
}

export interface ChatResponse {
  conversation_id: string;
  answer: string;
  tool_traces: ToolTrace[];
  findings: DiagnosticFinding[];
  budget: AgentBudgetMetadata;
}

export interface AgentBudgetMetadata {
  model_alias: string;
  model_call_count: number;
  max_model_calls: number | null;
  tool_call_count: number;
  max_tool_calls: number | null;
  tool_schema_count: number;
  log_line_count: number;
  token_budget: number | null;
  estimated_tokens_used: number | null;
  estimated_input_tokens: number | null;
  estimated_output_tokens: number | null;
  estimated_cost_usd: number | null;
  stopped_reason: string | null;
}

export interface ReadyResponse {
  status: string;
  checks: Record<string, boolean>;
  settings: {
    api_auth_configured: boolean;
    integrations: Record<string, boolean>;
    integration_details?: Record<string, IntegrationState>;
  };
}

export interface ApiEvent {
  id: string;
  timestamp: string;
  type: string;
  severity: string;
  source: string;
  payload_summary: string;
  correlation_id: string | null;
  data: Record<string, unknown>;
}

export interface IncidentSummary {
  id: string;
  created_at: string;
  updated_at: string;
  source: string;
  title: string;
  severity: string;
  status: string;
  correlation_id: string | null;
  pinned: boolean;
  event_count: number;
}

export interface IncidentTimelineEntry {
  timestamp: string;
  source: string;
  severity: string;
  summary: string;
  event_id: string | null;
  audit_id: string | null;
  evidence_summary: string | null;
  suggested_action: string | null;
}

export interface IncidentDetail {
  incident: IncidentSummary;
  timeline: IncidentTimelineEntry[];
}

export interface IntegrationState {
  name?: string;
  enabled: boolean;
  configured: boolean;
  missing_configuration: string[];
}

export interface CheckSummary {
  id: string;
  timestamp: string;
  source: string;
  status: string;
  severity: string;
  summary: string;
  correlation_id: string | null;
}

export interface DashboardSummary {
  readiness: Record<string, boolean>;
  integrations: Array<IntegrationState & { name: string }>;
  severity_counts: Record<string, number>;
  latest_checks: CheckSummary[];
  recent_events: ApiEvent[];
}

export interface ToolCapability {
  tool_name: string;
  description: string;
  safety: string;
  stage_behavior: string;
  integration: string | null;
  category: string;
  capability_ids: string[];
}

export interface IntegrationCapabilities {
  integration: string;
  enabled: boolean;
  configured: boolean;
  missing_configuration: string[];
  capabilities: ToolCapability[];
}

export interface ManifestTool {
  name: string;
  description: string;
  safety: string;
  capability_ids: string[];
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
}

export interface IntegrationManifest {
  id: string;
  name: string;
  version: string;
  category: string;
  enabled: boolean;
  configured: boolean;
  config_schema: {
    required?: string[];
    optional?: string[];
    secrets_redacted?: boolean;
  };
  capabilities: ToolCapability[];
  tools: ManifestTool[];
  resource_uris: string[];
  event_types: string[];
  diagnostic_bundles: string[];
  safety_posture: string;
  mcp_adapter_notes: string;
}

export function loginWithBearerToken(bearerToken: string) {
  return fetchApi<{ authenticated: boolean; cookie_name: string }>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ bearer_token: bearerToken }),
  });
}

export function logoutSession() {
  return fetchApi<{ authenticated: boolean; cookie_name: string }>('/auth/logout', {
    method: 'POST',
  });
}
