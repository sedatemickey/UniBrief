export function shanghai(value: string | null | undefined): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(value))
}

export function localIso(value: string): string {
  const date = new Date(value)
  return date.toISOString()
}

export const statusColor: Record<string, string> = {
  ACTIVE: 'green', UPDATED: 'blue', ARCHIVED: 'default', EXPIRED: 'red',
  PENDING: 'gold', PROCESSING: 'processing', PROCESSED: 'success', FAILED: 'error', IGNORED: 'default',
  UPCOMING: 'blue', ONGOING: 'cyan', COMPLETED: 'green', CANCELLED: 'default',
  DUE: 'red', READ: 'default', DISABLED: 'default', DOWNLOADED: 'green', DOWNLOADING: 'processing', SKIPPED: 'default',
}
