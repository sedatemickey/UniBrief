import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Badge, Button, Card, Descriptions, Space, Table, Tag, Typography } from 'antd'
import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { attachmentDownloadUrl, messageApi } from '../api'
import { ApiError } from '../api/client'
import { QueryState } from '../components/QueryState'
import type { Attachment, MessageItem } from '../api/types'
import { shanghai, statusColor } from '../utils/format'

export function MessagesPage() {
  const [params, setParams] = useSearchParams()
  const filters = useMemo(() => ({
    process_status: params.get('process_status') ?? undefined,
    keyword: params.get('keyword') ?? undefined,
    page: params.get('page') ? Number(params.get('page')) : 1,
    page_size: params.get('page_size') ? Number(params.get('page_size')) : 20,
  }), [params])
  const query = useQuery({ queryKey: ['messages', filters], queryFn: () => messageApi.list(filters) })
  return (
    <Card title="原始消息">
      <Space style={{ marginBottom: 16 }}>
        <select value={filters.process_status} onChange={(event) => { params.set('process_status', event.target.value); params.set('page', '1'); setParams(params) }}>
          {['', 'PENDING', 'PROCESSING', 'PROCESSED', 'FAILED', 'IGNORED'].map((item) => <option key={item} value={item}>{item || '全部状态'}</option>)}
        </select>
        <input defaultValue={filters.keyword} placeholder="关键词" onBlur={(event) => { params.set('keyword', event.target.value); params.set('page', '1'); setParams(params) }} />
      </Space>
      <QueryState loading={query.isLoading} error={query.error} empty={!query.data?.items.length}>
        <Table<MessageItem> rowKey="id" dataSource={query.data?.items ?? []} pagination={{ current: filters.page, pageSize: filters.page_size, total: query.data?.total ?? 0, onChange: (page) => { params.set('page', String(page)); setParams(params) } }} columns={[
          { title: 'ID', dataIndex: 'id', width: 70, render: (value) => <Link to={`/messages/${value}`}>{value}</Link> },
          { title: '内容', dataIndex: 'content', ellipsis: true }, { title: '发送时间', dataIndex: 'sent_at', render: shanghai },
          { title: '状态', dataIndex: 'process_status', render: (value) => <Badge color={statusColor[value]} text={value} /> },
        ]} />
      </QueryState>
    </Card>
  )
}

export function MessageDetailPage({ id, model }: { id: number; model?: string | null }) {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['message-detail', id], queryFn: () => messageApi.detail(id) })
  const analyze = useMutation({
    mutationFn: (mode: 'retry' | 'compare') => messageApi.analyze(id, { model, mode }),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['message-detail', id] }); queryClient.invalidateQueries({ queryKey: ['messages'] }) },
  })
  const retry = useMutation({
    mutationFn: (attachmentId: number) => messageApi.retryAttachment(attachmentId),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['message-detail', id] }),
  })
  return (
    <QueryState loading={query.isLoading} error={query.error}>
      {query.data && (
        <div className="page-stack">
          <Card title={`消息 #${id}`} extra={(
            <Space>
              {(query.data.process_status === 'PENDING' || query.data.process_status === 'FAILED') && <Button type="primary" loading={analyze.isPending} onClick={() => analyze.mutate('retry')}>AI 分析</Button>}
              {(query.data.process_status === 'PROCESSED' || query.data.process_status === 'IGNORED') && <Button loading={analyze.isPending} onClick={() => analyze.mutate('compare')}>模型对比</Button>}
            </Space>
          )}>
            {analyze.isError && <Alert type="error" showIcon title={analyze.error instanceof ApiError ? analyze.error.message : 'AI 调用失败'} style={{ marginBottom: 16 }} />}
            <Descriptions bordered column={3}>
              <Descriptions.Item label="渠道">{query.data.channel_name}</Descriptions.Item>
              <Descriptions.Item label="发送者">{query.data.sender_display_name}</Descriptions.Item>
              <Descriptions.Item label="状态"><Badge color={statusColor[query.data.process_status]} text={query.data.process_status} /></Descriptions.Item>
              <Descriptions.Item label="发送时间">{shanghai(query.data.sent_at)}</Descriptions.Item>
              <Descriptions.Item label="导入时间">{shanghai(query.data.ingested_at)}</Descriptions.Item>
              <Descriptions.Item label="外部 ID">{query.data.external_id}</Descriptions.Item>
            </Descriptions>
            <Typography.Paragraph style={{ marginTop: 16 }}>{query.data.content}</Typography.Paragraph>
          </Card>
          <Card title="附件">
            <Table<Attachment> rowKey="id" dataSource={query.data.attachments} pagination={false} columns={[
              { title: '文件', dataIndex: 'file_name' }, { title: '状态', dataIndex: 'download_status', render: (value) => <Badge color={statusColor[value]} text={value} /> },
              { title: '大小', dataIndex: 'file_size', render: (value: number | null) => value ? `${Math.round(value / 1024)} KB` : '—' },
              { title: '错误', dataIndex: 'last_error', ellipsis: true },
              { title: '操作', render: (_, item) => (
                <Space>
                  {item.download_status === 'DOWNLOADED' && <Button size="small" href={attachmentDownloadUrl(item.id)}>下载</Button>}
                  {(item.download_status === 'FAILED' || item.download_status === 'PENDING') && <Button size="small" loading={retry.isPending && retry.variables === item.id} onClick={() => retry.mutate(item.id)}>重试</Button>}
                </Space>
              )},
            ]} />
          </Card>
          <Card title="AI 分析历史">
            <Table rowKey="id" dataSource={query.data.analyses} pagination={false} columns={[
              { title: '模型', dataIndex: 'model_name' }, { title: '状态', dataIndex: 'status', render: (value) => <Tag color={value === 'SUCCEEDED' ? 'green' : 'red'}>{value}</Tag> },
              { title: '有价值', dataIndex: 'useful', render: (value) => value === null ? '—' : value ? '是' : '否' },
              { title: '耗时', dataIndex: 'latency_ms', render: (value) => value === null ? '—' : `${value} ms` },
              { title: '时间', dataIndex: 'analyzed_at', render: shanghai }, { title: '错误', dataIndex: 'error_message' },
            ]} />
          </Card>
        </div>
      )}
    </QueryState>
  )
}



