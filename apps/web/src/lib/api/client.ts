import { env } from '$env/dynamic/public';

export type ApiHealth = {
  service: string;
  status: string;
  version: string;
  timestamp: string;
};

const API_BASE_URL = env.PUBLIC_API_BASE_URL || 'http://localhost:8000';

export async function getHealth(fetcher: typeof fetch = fetch): Promise<ApiHealth> {
  const response = await fetcher(`${API_BASE_URL}/health`);

  if (!response.ok) {
    throw new Error(`API health check failed with ${response.status}`);
  }

  return response.json() as Promise<ApiHealth>;
}

export { API_BASE_URL };
