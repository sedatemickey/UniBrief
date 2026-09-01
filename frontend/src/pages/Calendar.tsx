import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Badge, Button, Card, DatePicker, Form, Modal, Select, Space, Table, Typography } from 'antd'
import dayjs from 'dayjs'
import { useMemo, useState } from 'react'
import { informationApi } from '../api'
import { ApiError } from '../api/client'
import { QueryState } from '../components/QueryState'
import type { EventDetail, EventItem, ReminderItem } from '../api/types'
import { shanghai, statusColor } from '../utils/format'


export function CalendarPage() {
  const [month, setMonth] = useState(dayjs().startOf('month'))
  const [editing, setEditing] = useState<EventDetail | null>(null)
  const [form] = Form.useForm()
  const range = useMemo(() => ({
    range_start: month.startOf('month').toISOString(),
    range_end: month.add(1, 'month').startOf('month').toISOString(),
  }), [month])
  const events = useQuery({ queryKey: ['events', range], queryFn: () => informationApi.events({ ...range, page_size: 100 }) })
  const queryClient = useQueryClient()
  const patch = useMutation({
    mutationFn: ({ id, values }: { id: number; values: Record<string, unknown> }) => informationApi.patchEvent(id, values),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['events'] }); queryClient.invalidateQueries({ queryKey: ['reminders'] }); setEditing(null) },
  })
  const days = Array.from({ length: month.daysInMonth() }, (_, index) => month.date(index + 1))
  const byDate = new Map<string, EventItem[]>()
  events.data?.items.forEach((event) => {
    const anchor = event.start_at ?? event.deadline
    if (anchor) {
      const key = dayjs(anchor).format('YYYY-MM-DD')
      byDate.set(key, [...(byDate.get(key) ?? []), event])
    }
  })
  return (
    <div className="page-stack">
      <Card title="事项日历" extra={(
        <Space>
          <Button onClick={() => setMonth(month.subtract(1, 'month'))}>上月</Button>
          <span>{month.format('YYYY 年 M 月')}</span>
          <Button onClick={() => setMonth(month.add(1, 'month'))}>下月</Button>
        </Space>
      )}>
        <QueryState loading={events.isLoading} error={events.error} empty={!events.data?.items.length}>
          <div className="calendar-grid">
            {['一', '二', '三', '四', '五', '六', '日'].map((label) => <div key={label} className="calendar-head">{label}</div>)}
            {days.map((day) => (
              <button type="button" key={day.toISOString()} className={`calendar-cell ${day.isSame(dayjs(), 'day') ? 'today' : ''}`}>
                <div className="calendar-date">{day.date()}</div>
                {(byDate.get(day.format('YYYY-MM-DD')) ?? []).map((event) => (
                  <span key={event.id} className={`calendar-event status-${event.event_status.toLowerCase()}`}>{event.title}</span>
                ))}
              </button>
            ))}
          </div>
        </QueryState>
      </Card>
      <Card title="议程时间线">
        <Table<EventItem> rowKey="id" dataSource={events.data?.items ?? []} columns={[
          { title: '事项', dataIndex: 'title' }, { title: '开始', dataIndex: 'start_at', render: shanghai },
          { title: '截止', dataIndex: 'deadline', render: shanghai }, { title: '状态', dataIndex: 'event_status', render: (value) => <Badge color={statusColor[value]} text={value} /> },
          { title: '操作', render: (_, item) => <Button size="small" onClick={async () => { const detail = await informationApi.event(item.id); setEditing(detail); form.setFieldsValue({ start_at: detail.start_at ? dayjs(detail.start_at) : null, deadline: detail.deadline ? dayjs(detail.deadline) : null }) }}>编辑</Button> },
        ]} />
      </Card>
      <Modal title={editing?.title} open={!!editing} onCancel={() => setEditing(null)} onOk={() => form.submit()} confirmLoading={patch.isPending}>
        {patch.isError && <Alert type="error" showIcon title={patch.error instanceof ApiError ? patch.error.message : '保存失败'} />}
        <Form form={form} layout="vertical" onFinish={(values) => editing && patch.mutate({ id: editing.id, values: { ...values, expected_information_version: editing.information_version } })}>
          <Form.Item name="start_at" label="开始时间"><DatePicker showTime style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="deadline" label="截止时间"><DatePicker showTime style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="event_status" label="状态"><Select allowClear options={['UPCOMING', 'COMPLETED', 'CANCELLED'].map((x) => ({ value: x }))} /></Form.Item>
          <Typography.Paragraph type="secondary">留空表示清空对应时间；保存后至少需要保留一个时间。</Typography.Paragraph>
        </Form>
      </Modal>
    </div>
  )
}

export function RemindersPage() {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<string | undefined>()
  const reminders = useQuery({ queryKey: ['reminders', status], queryFn: () => informationApi.reminders({ status, page_size: 100 }), refetchInterval: 60_000 })
  const action = useMutation({
    mutationFn: ({ id, values }: { id: number; values: Record<string, unknown> }) => informationApi.patchReminder(id, values),
    onSuccess: async () => await queryClient.invalidateQueries({ queryKey: ['reminders'] }),
  })
  const read = useMutation({ mutationFn: informationApi.readReminder, onSuccess: async () => await queryClient.invalidateQueries({ queryKey: ['reminders'] }) })
  return (
    <Card title="站内提醒中心" extra={<Typography.Text type="secondary">每 60 秒自动刷新</Typography.Text>}>
      <Space style={{ marginBottom: 16 }}>
        <Select allowClear placeholder="状态" style={{ width: 160 }} value={status} onChange={setStatus} options={['PENDING', 'DUE', 'READ', 'DISABLED'].map((x) => ({ value: x }))} />
        {action.isError && <Alert type="error" title={action.error instanceof ApiError ? action.error.message : '操作失败'} />}
      </Space>
      <QueryState loading={reminders.isLoading} error={reminders.error} empty={!reminders.data?.items.length}>
        <Table<ReminderItem> rowKey="id" dataSource={reminders.data?.items ?? []} pagination={false} columns={[
          { title: '事项', dataIndex: 'title' }, { title: '提醒时间', dataIndex: 'remind_at', render: shanghai },
          { title: '截止时间', dataIndex: 'deadline', render: shanghai }, { title: '状态', dataIndex: 'reminder_status' },
          { title: '自定义', dataIndex: 'is_custom_time', render: (value) => value ? '是' : '否' },
          { title: '操作', render: (_, item) => (
            <Space>
              <Button size="small" onClick={() => { const value = window.prompt('输入提醒时间（ISO 8601）', item.remind_at); if (value) action.mutate({ id: item.id, values: { remind_at: value } }) }}>修改时间</Button>
              <Button size="small" onClick={() => action.mutate({ id: item.id, values: { enabled: item.reminder_status === 'DISABLED' } })}>{item.reminder_status === 'DISABLED' ? '重新启用' : '关闭'}</Button>
              <Button size="small" disabled={item.reminder_status !== 'DUE'} loading={read.isPending && read.variables === item.id} onClick={() => read.mutate(item.id)}>标记已读</Button>
            </Space>
          )},
        ]} />
      </QueryState>
    </Card>
  )
}




