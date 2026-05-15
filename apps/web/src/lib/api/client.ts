import { env } from '$env/dynamic/public';

export type ApiHealth = {
  service: string;
  status: string;
  version: string;
  timestamp: string;
};

export type User = {
  id: string;
  email: string;
  created_at: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type Project = {
  id: string;
  user_id: string;
  name: string;
  slug: string;
  description: string | null;
  environment_default: string;
  created_at: string;
  updated_at: string;
};

export type ApiKey = {
  id: string;
  project_id: string;
  name: string;
  key_prefix: string;
  masked_key: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
  is_revoked: boolean;
};

export type ApiKeyCreateResponse = {
  id: string;
  name: string;
  key_prefix: string;
  raw_key: string;
  created_at: string;
};

export type ProcessedEvent = {
  event_id: string;
  project_id: string;
  api_key_prefix: string;
  timestamp: string;
  received_at: string;
  service: string;
  environment: string;
  level: string;
  message: string;
  normalized_message: string;
  fingerprint_hash: string;
  status_code: number | null;
  latency_ms: number | null;
  trace_id: string | null;
  request_id: string | null;
  metadata: Record<string, unknown>;
};

export type MetricBucket = {
  bucketStart: string;
  service: string;
  environment: string;
  totalEvents: number;
  errorEvents: number;
  warningEvents: number;
  fatalEvents: number;
  errorRate: number;
  latencyAvgMs: number | null;
  latencyP95Ms: number | null;
};

export type MetricsResponse = {
  range: string;
  bucketSize: number;
  summary: {
    totalEvents: number;
    errorEvents: number;
    warningEvents: number;
    fatalEvents: number;
    latencyP95Ms: number | null;
    errorRate: number;
    activeIncidents: number;
  };
  series: MetricBucket[];
  services: string[];
  topServices: Array<{
    service: string;
    totalEvents: number;
    errorEvents: number;
    fatalEvents: number;
    errorRate: number;
  }>;
};

const API_BASE_URL = env.PUBLIC_API_BASE_URL || 'http://localhost:8000';

async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  token = ''
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = body?.error?.message ?? `Request failed with ${response.status}`;
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export async function getHealth(fetcher: typeof fetch = fetch): Promise<ApiHealth> {
  const response = await fetcher(`${API_BASE_URL}/health`);

  if (!response.ok) {
    throw new Error(`API health check failed with ${response.status}`);
  }

  return response.json() as Promise<ApiHealth>;
}

export function register(email: string, password: string): Promise<AuthResponse> {
  return apiRequest<AuthResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password })
  });
}

export function login(email: string, password: string): Promise<AuthResponse> {
  return apiRequest<AuthResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password })
  });
}

export function getMe(token: string): Promise<User> {
  return apiRequest<User>('/auth/me', {}, token);
}

export function listProjects(token: string): Promise<Project[]> {
  return apiRequest<Project[]>('/projects', {}, token);
}

export function createProject(
  token: string,
  payload: { name: string; description?: string; environment_default?: string }
): Promise<Project> {
  return apiRequest<Project>(
    '/projects',
    {
      method: 'POST',
      body: JSON.stringify(payload)
    },
    token
  );
}

export function listApiKeys(token: string, projectId: string): Promise<ApiKey[]> {
  return apiRequest<ApiKey[]>(`/projects/${projectId}/api-keys`, {}, token);
}

export function createApiKey(
  token: string,
  projectId: string,
  payload: { name: string; mode?: 'demo' | 'live' }
): Promise<ApiKeyCreateResponse> {
  return apiRequest<ApiKeyCreateResponse>(
    `/projects/${projectId}/api-keys`,
    {
      method: 'POST',
      body: JSON.stringify(payload)
    },
    token
  );
}

export function revokeApiKey(token: string, keyId: string): Promise<ApiKey> {
  return apiRequest<ApiKey>(
    `/api-keys/${keyId}`,
    {
      method: 'DELETE'
    },
    token
  );
}

export function listEvents(
  token: string,
  projectId: string,
  filters: {
    service?: string;
    environment?: string;
    level?: string;
    search?: string;
    start?: string;
    end?: string;
  } = {}
): Promise<{ events: ProcessedEvent[] }> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) {
      params.set(key, value);
    }
  }
  const suffix = params.toString() ? `?${params.toString()}` : '';
  return apiRequest<{ events: ProcessedEvent[] }>(`/projects/${projectId}/events${suffix}`, {}, token);
}

export function getProjectMetrics(
  token: string,
  projectId: string,
  filters: { range?: string; service?: string; environment?: string; bucketSize?: number } = {}
): Promise<MetricsResponse> {
  const params = new URLSearchParams();
  if (filters.range) params.set('range', filters.range);
  if (filters.service) params.set('service', filters.service);
  if (filters.environment) params.set('environment', filters.environment);
  if (filters.bucketSize) params.set('bucketSize', String(filters.bucketSize));
  const suffix = params.toString() ? `?${params.toString()}` : '';
  return apiRequest<MetricsResponse>(`/projects/${projectId}/metrics${suffix}`, {}, token);
}

export { API_BASE_URL };
