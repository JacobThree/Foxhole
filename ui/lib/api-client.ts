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
}

export interface IntegrationCapabilities {
  integration: string;
  enabled: boolean;
  configured: boolean;
  missing_configuration: string[];
  capabilities: ToolCapability[];
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
