import { api, queryString } from './client'
import type {
  AIConfig, Attachment, Category, CategoryStatistic, Channel, ChannelStatistic, EventDetail, EventItem, InformationDetail, InformationItem, MessageDetail, MessageItem, Page, Platform, ReminderItem, Sender, StatisticsOverview, TagItem, TagStatistic, User,
} from './types'

export interface RegistrationStatus { enabled: boolean }
export interface AIModels { supports_listing: boolean; models: Array<{ id: string }>; error_code: string | null; message: string | null }
export interface AITestResult { ok: boolean; model: string; latency_ms: number; message: string }
export interface ImportResult { received: number; inserted: number; duplicates: number; failed: number; attachment_metadata_created: number; attachment_downloads_scheduled: number; results: Array<{ external_id: string; status: string; message_id: number | null; error: { code: string; message: string; retryable: boolean } | null }> }
export interface AnalyzeBatchResult { mode: string; results: Array<{ message_id: number; status: string; analysis_id: number | null; business_applied: boolean; information_ids: number[]; error: { code: string; retryable: boolean; message: string | null } | null }> }
export interface UpcomingEvents { days: number; total: number; by_date: Array<{ date: string; count: number }> }

export const authApi = {
  registrationStatus: () => api<RegistrationStatus>('/auth/registration-status'),
  login: (json: { username: string; password: string }) => api<User>('/auth/login', { method: 'POST', json }),
  register: (json: { username: string; display_name: string; password: string }) => api<User>('/auth/register', { method: 'POST', json }),
  me: () => api<User>('/auth/me'),
  logout: () => api<void>('/auth/logout', { method: 'POST' }),
  changePassword: (json: { current_password: string; new_password: string }) => api<void>('/auth/change-password', { method: 'POST', json }),
}

export const adminApi = {
  login: (json: { password: string }) => api<{ authenticated: boolean }>('/admin/auth/login', { method: 'POST', admin: true, json }),
  me: () => api<{ authenticated: boolean }>('/admin/auth/me', { admin: true }),
  logout: () => api<void>('/admin/auth/logout', { method: 'POST', admin: true }),
  changePassword: (json: { current_password: string; new_password: string }) => api<void>('/admin/auth/change-password', { method: 'POST', admin: true, json }),
  users: (params: Record<string, string | number>) => api<Page<User>>(`/admin/users${queryString(params)}`, { admin: true }),
  createUser: (json: { username: string; display_name: string; password: string }) => api<User>('/admin/users', { method: 'POST', admin: true, json }),
  patchUser: (id: number, json: { display_name?: string; status?: 'ACTIVE' | 'DISABLED' }) => api<User>(`/admin/users/${id}`, { method: 'PATCH', admin: true, json }),
  resetPassword: (id: number, json: { new_password: string }) => api<void>(`/admin/users/${id}/reset-password`, { method: 'POST', admin: true, json }),
  settings: () => api<{ registration_enabled: boolean; admin_password_configured: boolean }>('/admin/settings', { admin: true }),
  registration: (json: { enabled: boolean }) => api<RegistrationStatus>('/admin/settings/registration', { method: 'PATCH', admin: true, json }),
  platforms: (params: Record<string, string | number> = {}) => api<Page<Platform>>(`/admin/platforms${queryString(params)}`, { admin: true }),
  createPlatform: (json: { name: string; type: string; status?: 'ACTIVE' | 'DISABLED' }) => api<Platform>('/admin/platforms', { method: 'POST', admin: true, json }),
  patchPlatform: (id: number, json: { name?: string; type?: string; status?: 'ACTIVE' | 'DISABLED' }) => api<Platform>(`/admin/platforms/${id}`, { method: 'PATCH', admin: true, json }),
  categories: (params: Record<string, string | number> = {}) => api<Page<Category>>(`/admin/categories${queryString(params)}`, { admin: true }),
  createCategory: (json: { name: string; description?: string | null; status?: 'ACTIVE' | 'DISABLED' }) => api<Category>('/admin/categories', { method: 'POST', admin: true, json }),
  patchCategory: (id: number, json: { name?: string; description?: string | null; status?: 'ACTIVE' | 'DISABLED' }) => api<Category>(`/admin/categories/${id}`, { method: 'PATCH', admin: true, json }),
}

export const dictionaryApi = {
  platforms: () => api<{ items: Platform[] }>('/platforms'),
  categories: () => api<{ items: Category[] }>('/categories'),
}

export const sourceApi = {
  channels: (params: Record<string, string | number> = {}) => api<Page<Channel>>(`/channels${queryString(params)}`),
  createChannel: (json: { platform_id: number; external_id: string; name: string; channel_type: string }) => api<Channel>('/channels', { method: 'POST', json }),
  patchChannel: (id: number, json: { name?: string; channel_type?: string }) => api<Channel>(`/channels/${id}`, { method: 'PATCH', json }),
  senders: (params: Record<string, string | number> = {}) => api<Page<Sender>>(`/senders${queryString(params)}`),
  createSender: (json: { platform_id: number; external_id: string; display_name: string; source_type: string; credibility: number }) => api<Sender>('/senders', { method: 'POST', json }),
  patchSender: (id: number, json: { display_name?: string; source_type?: string; credibility?: number }) => api<Sender>(`/senders/${id}`, { method: 'PATCH', json }),
}

export const messageApi = {
  list: (params: Record<string, string | number | boolean | Array<string | number> | undefined>) => api<Page<MessageItem>>(`/messages${queryString(params)}`),
  detail: (id: number) => api<MessageDetail>(`/messages/${id}`),
  importJson: (json: unknown) => api<ImportResult>('/messages/import', { method: 'POST', json }),
  analyze: (id: number, json: { model?: string | null; mode: 'retry' | 'compare' }) => api<{ message_id: number; process_status: string; analysis_id: number; model_name: string; useful: boolean; information_ids: number[]; business_applied: boolean }>(`/messages/${id}/analyze`, { method: 'POST', json }),
  analyzeBatch: (json: { message_ids: number[]; model?: string | null; mode: 'retry' | 'compare' }) => api<AnalyzeBatchResult>('/messages/analyze-batch', { method: 'POST', json }),
  retryAttachment: (id: number) => api<Attachment>(`/attachments/${id}/retry-download`, { method: 'POST' }),
}

export const aiApi = {
  config: () => api<AIConfig>('/ai/config'),
  models: () => api<AIModels>('/ai/models'),
  test: (model: string) => api<AITestResult>('/ai/test', { method: 'POST', json: { model } }),
}

export const informationApi = {
  list: (params: Record<string, string | number | Array<string | number> | undefined>) => api<Page<InformationItem>>(`/information${queryString(params)}`),
  detail: (id: number) => api<InformationDetail>(`/information/${id}`),
  patch: (id: number, json: Record<string, unknown>) => api<InformationDetail>(`/information/${id}`, { method: 'PATCH', json }),
  tags: (params: Record<string, string | number> = {}) => api<Page<TagItem>>(`/tags${queryString(params)}`),
  events: (params: Record<string, string | number | undefined>) => api<Page<EventItem>>(`/events${queryString(params)}`),
  event: (id: number) => api<EventDetail>(`/events/${id}`),
  patchEvent: (id: number, json: Record<string, unknown>) => api<unknown>(`/events/${id}`, { method: 'PATCH', json }),
  reminders: (params: Record<string, string | number | undefined> = {}) => api<Page<ReminderItem>>(`/reminders${queryString(params)}`),
  patchReminder: (id: number, json: Record<string, unknown>) => api<ReminderItem>(`/reminders/${id}`, { method: 'PATCH', json }),
  readReminder: (id: number) => api<ReminderItem>(`/reminders/${id}/read`, { method: 'POST' }),
}

export const statisticsApi = {
  overview: (params: Record<string, string | undefined> = {}) => api<StatisticsOverview>(`/statistics/overview${queryString(params)}`),
  channels: (params: Record<string, string | number | undefined>) => api<ChannelStatistic[]>(`/statistics/channels${queryString(params)}`),
  categories: (params: Record<string, string | number | boolean | undefined>) => api<CategoryStatistic[]>(`/statistics/categories${queryString(params)}`),
  tags: (params: Record<string, string | number | boolean | undefined>) => api<TagStatistic[]>(`/statistics/tags${queryString(params)}`),
  upcoming: (params: Record<string, number>) => api<UpcomingEvents>(`/statistics/upcoming-events${queryString(params)}`),
}

export function attachmentDownloadUrl(id: number): string { return `/api/v1/attachments/${id}/download` }


export { api }




