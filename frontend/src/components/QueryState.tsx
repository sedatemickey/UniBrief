import { Alert, Empty, Spin } from 'antd'
import type { ReactNode } from 'react'

export function QueryState({ loading, error, empty, children }: { loading: boolean; error: unknown; empty?: boolean; children: ReactNode }) {
  if (loading) return <div className="query-state"><Spin description="加载中…" /></div>
  if (error) return <Alert type="error" showIcon title="加载失败" description={error instanceof Error ? error.message : '请稍后重试'} />
  if (empty) return <Empty description="暂无数据" />
  return <>{children}</>
}


