export interface HealthResponse {
  status: 'ok'
  service: string
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch('/health', {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) {
    throw new Error(`健康检查失败（HTTP ${response.status}）`)
  }

  return (await response.json()) as HealthResponse
}
