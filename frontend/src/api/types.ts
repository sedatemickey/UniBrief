export interface ApiEnvelopeError {
  error: {
    code: string
    message: string
    retryable: boolean
    details?: unknown
    request_id?: string
  }
}

export interface User {
  id: number
  username: string
  display_name: string
  status: string
}

export interface Page<T> {
  items: T[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface NamedResource { id: number; name: string }
export interface EventSummary { id: number; start_at: string | null; deadline: string | null; event_status: string }
export interface InformationItem {
  id: number; title: string; summary: string; source_type: string; importance: number
  confidence: number; status: string; version: number; created_at: string; updated_at: string
  categories: NamedResource[]; tags: NamedResource[]; event: EventSummary | null
}
export interface InformationDetail extends InformationItem {
  reminder: Reminder | null
  sources: Array<{ message_id: number; relation_type: string; content: string; sent_at: string; channel_name: string; sender_display_name: string }>
}
export interface Attachment { id: number; message_id: number; file_name: string; file_type: string | null; file_size: number | null; sha256: string | null; download_status: string; download_attempts: number; downloaded_at: string | null; last_error: string | null }
export interface MessageItem { id: number; channel_id: number; sender_id: number; external_id: string; content: string; sent_at: string; ingested_at: string; process_status: string; processing_started_at: string | null }
export interface MessageDetail extends MessageItem { platform_id: number; channel_name: string; sender_display_name: string; attachments: Attachment[]; analyses: Array<{ id: number; model_name: string; status: string; useful: boolean | null; error_code: string | null; error_message: string | null; latency_ms: number | null; analyzed_at: string }> }
export interface Channel { id: number; platform_id: number; external_id: string; name: string; channel_type: string; created_at: string }
export interface Sender { id: number; platform_id: number; external_id: string; display_name: string; source_type: string; credibility: number; created_at: string }
export interface Platform { id: number; name: string; type: string; status: string; created_at: string }
export interface Category { id: number; name: string; description: string | null; status: string; created_at: string }
export interface TagItem { id: number; name: string; created_at: string }
export interface Reminder { id: number; remind_at: string; reminder_status: string; is_custom_time: boolean; triggered_at: string | null; read_at: string | null }
export interface ReminderItem extends Reminder { event_id: number; information_id: number; title: string; deadline: string | null }
export interface EventItem { id: number; information_id: number; information_version: number; title: string; importance: number; start_at: string | null; deadline: string | null; event_status: string; updated_at: string }
export interface AIConfig { base_url: string; default_model: string; timeout_seconds: number; max_retries: number; has_api_key: boolean }
export interface StatisticsOverview { message_total: number; information_active_total: number; event_upcoming_total: number; reminder_due_total: number }
export interface ChannelStatistic { channel_id: number; channel_name: string; platform_id: number; platform_name: string; message_count: number; effective_message_count: number; effectiveness_rate: number }
export interface CategoryStatistic { category_id: number; category_name: string; information_count: number }
export interface TagStatistic { tag_id: number; tag_name: string; usage_count: number }
export interface EventDetail extends EventItem { summary: string; reminder: Reminder | null }

