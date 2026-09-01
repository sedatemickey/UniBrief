import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, DatePicker, Button, Card, Descriptions, Drawer, Form, Input, InputNumber, Select, Table, Tag, Typography } from 'antd'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import dayjs from 'dayjs'
import { dictionaryApi, informationApi } from '../api'
import { ApiError } from '../api/client'
import { QueryState } from '../components/QueryState'
import type { InformationItem } from '../api/types'
import { shanghai, statusColor } from '../utils/format'

export function InformationPage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const categories = useQuery({ queryKey: ['categories'], queryFn: dictionaryApi.categories })
  const tags = useQuery({ queryKey: ['tags'], queryFn: () => informationApi.tags({ page_size: 100 }) })
  const filters = useMemo(() => ({
    category_ids: params.getAll('category_ids').map(Number),
    tag_ids: params.getAll('tag_ids').map(Number),
    importance_min: params.get('importance_min') ? Number(params.get('importance_min')) : undefined,
    importance_max: params.get('importance_max') ? Number(params.get('importance_max')) : undefined,
    status: params.get('status') ?? undefined,
    created_from: params.get('created_from') ?? undefined,
    created_to: params.get('created_to') ?? undefined,
    event_from: params.get('event_from') ?? undefined,
    event_to: params.get('event_to') ?? undefined,
    keyword: params.get('keyword') ?? undefined,
    sort: params.get('sort') ?? 'created_at_desc',
    page: params.get('page') ? Number(params.get('page')) : 1,
    page_size: params.get('page_size') ? Number(params.get('page_size')) : 20,
  }), [params])
  const initialValues = {
    ...filters,
    created_range: filters.created_from && filters.created_to
      ? [dayjs(filters.created_from), dayjs(filters.created_to)]
      : undefined,
    event_range: filters.event_from && filters.event_to
      ? [dayjs(filters.event_from), dayjs(filters.event_to)]
      : undefined,
  }
  const query = useQuery({ queryKey: ['information', filters], queryFn: () => informationApi.list(filters) })
  const update = (rawValues: Record<string, unknown>) => {
    const createdRange = rawValues.created_range as [dayjs.Dayjs, dayjs.Dayjs] | undefined
    const eventRange = rawValues.event_range as [dayjs.Dayjs, dayjs.Dayjs] | undefined
    const values = { ...filters, ...rawValues } as Record<string, unknown>
    if (createdRange) { values.created_from = createdRange[0].toISOString(); values.created_to = createdRange[1].toISOString() }
    if (eventRange) { values.event_from = eventRange[0].toISOString(); values.event_to = eventRange[1].toISOString() }
    delete values.created_range
    delete values.event_range
    const next = new URLSearchParams()
    Object.entries(values).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') return
      if (Array.isArray(value)) value.forEach((item) => next.append(key, String(item)))
      else next.set(key, String(value))
    })
    if (!next.get('page')) next.set('page', '1')
    setParams(next)
  }
  return (
    <div className="page-stack">
      <Card title="有效信息">
        <Form layout="inline" initialValues={initialValues} onFinish={update} className="filter-form">
          <Form.Item name="keyword"><Input allowClear placeholder="关键词" /></Form.Item>
          <Form.Item name="category_ids"><Select allowClear mode="multiple" placeholder="分类" style={{ minWidth: 160 }} loading={categories.isLoading} options={categories.data?.items.map((x) => ({ value: x.id, label: x.name }))} /></Form.Item>
          <Form.Item name="tag_ids"><Select allowClear mode="multiple" placeholder="标签（任一匹配）" style={{ minWidth: 180 }} loading={tags.isLoading} options={tags.data?.items.map((x) => ({ value: x.id, label: x.name }))} /></Form.Item>
          <Form.Item name="importance_min"><InputNumber min={1} max={5} placeholder="最小重要度" /></Form.Item>
          <Form.Item name="importance_max"><InputNumber min={1} max={5} placeholder="最大重要度" /></Form.Item>
          <Form.Item name="status"><Select allowClear placeholder="状态" style={{ width: 120 }} options={['ACTIVE', 'UPDATED', 'EXPIRED', 'ARCHIVED'].map((x) => ({ value: x, label: x }))} /></Form.Item>
          <Form.Item name="created_range"><DatePicker.RangePicker showTime placeholder={['信息开始', '信息结束']} /></Form.Item>
          <Form.Item name="event_range"><DatePicker.RangePicker showTime placeholder={['事项开始', '事项结束']} /></Form.Item>
          <Form.Item name="sort"><Select style={{ width: 170 }} options={[
            { value: 'created_at_desc', label: '创建时间降序' }, { value: 'updated_at_desc', label: '更新时间降序' },
            { value: 'importance_desc', label: '重要度降序' }, { value: 'deadline_asc', label: '截止时间升序' },
          ]} /></Form.Item>
          <Button htmlType="submit" type="primary">筛选</Button>
          <Button onClick={() => navigate('/information')}>重置</Button>
        </Form>
      </Card>
      <Card>
        <QueryState loading={query.isLoading} error={query.error} empty={!query.data?.items.length}>
          <Table<InformationItem>
            rowKey="id"
            dataSource={query.data?.items ?? []}
            pagination={{ current: filters.page, pageSize: filters.page_size, total: query.data?.total ?? 0, showSizeChanger: true, onChange: (page, size) => update({ ...filters, page, page_size: size }) }}
            columns={[
              { title: '标题', dataIndex: 'title', render: (_, item) => <Link to={`/information/${item.id}`}>{item.title}</Link> },
              { title: '重要度', dataIndex: 'importance', width: 90, render: (value) => <Tag color={value >= 5 ? 'red' : value >= 4 ? 'orange' : 'blue'}>{value}</Tag> },
              { title: '分类', dataIndex: 'categories', render: (values: InformationItem['categories']) => values.map((x) => <Tag key={x.id}>{x.name}</Tag>) },
              { title: '标签', dataIndex: 'tags', render: (values: InformationItem['tags']) => values.map((x) => <Tag key={x.id} color="processing">{x.name}</Tag>) },
              { title: '事项截止', dataIndex: ['event', 'deadline'], render: (value: string | null) => shanghai(value) },
              { title: '状态', dataIndex: 'status', render: (value) => <Tag color={statusColor[value]}>{value}</Tag> },
              { title: '创建时间', dataIndex: 'created_at', render: shanghai },
            ]}
          />
        </QueryState>
      </Card>
    </div>
  )
}

export function InformationDetailPage({ id }: { id: number }) {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['information-detail', id], queryFn: () => informationApi.detail(id) })
  const [form] = Form.useForm()
  const [open, setOpen] = useState(false)
  const save = useMutation({
    mutationFn: (values: Record<string, unknown>) => informationApi.patch(id, values),
    onSuccess: async () => { setOpen(false); await queryClient.invalidateQueries({ queryKey: ['information-detail', id] }); queryClient.invalidateQueries({ queryKey: ['information'] }) },
  })
  return (
    <QueryState loading={query.isLoading} error={query.error}>
      {query.data && (
        <div className="page-stack">
          <Card title={query.data.title} extra={<Button onClick={() => { form.setFieldsValue({ title: query.data!.title, summary: query.data!.summary, importance: query.data!.importance, status: query.data!.status }); setOpen(true) }}>编辑信息</Button>}>
            <Descriptions bordered column={3}>
              <Descriptions.Item label="状态"><Tag color={statusColor[query.data.status]}>{query.data.status}</Tag></Descriptions.Item>
              <Descriptions.Item label="重要度">{query.data.importance}</Descriptions.Item>
              <Descriptions.Item label="置信度">{query.data.confidence}</Descriptions.Item>
              <Descriptions.Item label="创建时间">{shanghai(query.data.created_at)}</Descriptions.Item>
              <Descriptions.Item label="更新时间">{shanghai(query.data.updated_at)}</Descriptions.Item>
              <Descriptions.Item label="版本">{query.data.version}</Descriptions.Item>
              <Descriptions.Item label="分类" span={3}>{query.data.categories.length ? query.data.categories.map((item) => <Tag key={item.id}>{item.name}</Tag>) : '—'}</Descriptions.Item>
              <Descriptions.Item label="标签" span={3}>{query.data.tags.length ? query.data.tags.map((item) => <Tag key={item.id} color="processing">{item.name}</Tag>) : '—'}</Descriptions.Item>
              <Descriptions.Item label="事项开始">{shanghai(query.data.event?.start_at)}</Descriptions.Item>
              <Descriptions.Item label="事项截止">{shanghai(query.data.event?.deadline)}</Descriptions.Item>
              <Descriptions.Item label="事项状态">{query.data.event?.event_status ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="提醒时间">{shanghai(query.data.reminder?.remind_at)}</Descriptions.Item>
              <Descriptions.Item label="提醒状态">{query.data.reminder?.reminder_status ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="自定义提醒">{query.data.reminder ? (query.data.reminder.is_custom_time ? '是' : '否') : '—'}</Descriptions.Item>
            </Descriptions>
            <Typography.Paragraph style={{ marginTop: 16 }}>{query.data.summary}</Typography.Paragraph>
          </Card>
          <Card title="原始来源证据">
            <Table rowKey="message_id" dataSource={query.data.sources} columns={[
              { title: '消息', dataIndex: 'message_id', render: (value) => <Link to={`/messages/${value}`}>#{value}</Link> },
              { title: '关系', dataIndex: 'relation_type' }, { title: '发送者', dataIndex: 'sender_display_name' },
              { title: '渠道', dataIndex: 'channel_name' }, { title: '时间', dataIndex: 'sent_at', render: shanghai }, { title: '原文', dataIndex: 'content' },
            ]} pagination={false} />
          </Card>
          <Drawer open={open} title="编辑信息" onClose={() => setOpen(false)} size={520}>
            <Form form={form} layout="vertical" onFinish={(values) => save.mutate({ ...values, expected_version: query.data!.version })}>
              {save.isError && <Alert type="error" showIcon title={save.error instanceof ApiError ? save.error.message : '保存失败'} style={{ marginBottom: 16 }} />}
              <Form.Item name="title" label="标题"><Input /></Form.Item>
              <Form.Item name="summary" label="摘要"><Input.TextArea rows={5} /></Form.Item>
              <Form.Item name="importance" label="重要度"><InputNumber min={1} max={5} /></Form.Item>
              <Form.Item name="status" label="状态"><Select options={['ACTIVE', 'UPDATED', 'EXPIRED', 'ARCHIVED'].map((x) => ({ value: x }))} /></Form.Item>
              <Button htmlType="submit" type="primary" loading={save.isPending}>保存</Button>
            </Form>
          </Drawer>
        </div>
      )}
    </QueryState>
  )
}





