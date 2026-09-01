import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Card, Input, Select, Space, Table, Typography, Upload } from 'antd'
import { useState } from 'react'
import { aiApi, api, messageApi } from '../api'
import { ApiError } from '../api/client'
import { QueryState } from '../components/QueryState'
import { useAIDefault, useModel } from '../hooks/useModel'
import type { MessageItem } from '../api/types'
import { shanghai } from '../utils/format'

const sample = {
  platform: { name: 'QQ', type: 'IM' },
  channel: { external_id: 'class-001', name: '数据库课程群', channel_type: 'GROUP' },
  messages: [{ external_id: 'notice-001', sender: { external_id: 'teacher-001', display_name: '张老师', source_type: 'TEACHER' }, content: '数据库课程设计报告请在 9 月 20 日前提交。', sent_at: new Date().toISOString(), attachments: [] }],
}

export function ImportAnalyzePage() {
  const queryClient = useQueryClient()
  const config = useAIDefault()
  const { model, setModel } = useModel()
  const [text, setText] = useState(JSON.stringify(sample, null, 2))
  const [selected, setSelected] = useState<number[]>([])
  const [upload, setUpload] = useState<File | null>(null)
  const models = useQuery({ queryKey: ['ai-models'], queryFn: aiApi.models })
  const messages = useQuery({ queryKey: ['messages', 'import'], queryFn: () => messageApi.list({ page: 1, page_size: 100 }) })
  const jsonImport = useMutation({
    mutationFn: async () => messageApi.importJson(JSON.parse(text)),
    onSuccess: async () => await queryClient.invalidateQueries({ queryKey: ['messages'] }),
  })
  const csvImport = useMutation({
    mutationFn: async (file: File) => {
      const body = new FormData()
      body.append('file', file)
      return api<unknown>('/messages/import-csv', { method: 'POST', body })
    },
    onSuccess: async () => await queryClient.invalidateQueries({ queryKey: ['messages'] }),
  })
  const analyze = useMutation({
    mutationFn: (mode: 'retry' | 'compare') => messageApi.analyzeBatch({ message_ids: selected, model, mode }),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['messages'] }); queryClient.invalidateQueries({ queryKey: ['information'] }) },
  })
  return (
    <div className="page-stack">
      <Card title="导入消息">
        <Space orientation="vertical" style={{ width: '100%' }} size="middle">
          <Input.TextArea rows={12} value={text} onChange={(event) => setText(event.target.value)} />
          <Space>
            <Button type="primary" loading={jsonImport.isPending} onClick={() => jsonImport.mutate()}>导入 JSON</Button>
            <Upload maxCount={1} beforeUpload={(file) => { setUpload(file); return false }}><Button>选择 CSV</Button></Upload>
            <Button disabled={!upload} loading={csvImport.isPending} onClick={() => upload && csvImport.mutate(upload)}>导入 CSV</Button>
          </Space>
          {jsonImport.isError && <Alert type="error" showIcon title={jsonImport.error instanceof SyntaxError ? 'JSON 格式错误' : jsonImport.error instanceof ApiError ? jsonImport.error.message : '导入失败'} />}
          {jsonImport.isSuccess && <Alert type="success" showIcon title={`接收 ${jsonImport.data.received}，新增 ${jsonImport.data.inserted}，重复 ${jsonImport.data.duplicates}，失败 ${jsonImport.data.failed}`} />}
          {csvImport.isError && <Alert type="error" showIcon title={csvImport.error instanceof ApiError ? csvImport.error.message : 'CSV 导入失败'} />}
        </Space>
      </Card>
      <Card title="分析与重试" extra={<Typography.Text type="secondary">AI Key 状态：{config.data?.has_api_key ? '已配置' : '未配置'}</Typography.Text>}>
        <Space style={{ marginBottom: 16 }}>
          <Select style={{ width: 300 }} value={model ?? config.data?.default_model ?? undefined} showSearch allowClear placeholder="选择或搜索模型" options={models.data?.models.map((item) => ({ value: item.id, label: item.id })) ?? []} onChange={setModel} />
          <Input style={{ width: 300 }} value={model ?? config.data?.default_model ?? ''} placeholder="手工输入模型 ID" onChange={(event) => setModel(event.target.value)} />
          <Button type="primary" disabled={!selected.length} loading={analyze.isPending} onClick={() => analyze.mutate('retry')}>批量 retry 分析</Button>
          <Button disabled={!selected.length} loading={analyze.isPending} onClick={() => analyze.mutate('compare')}>批量 compare</Button>
        </Space>
        {analyze.isError && <Alert type="error" showIcon title={analyze.error instanceof ApiError ? analyze.error.message : '分析失败'} />}
        {analyze.isSuccess && <Alert type={analyze.data.results.every((x) => x.error === null) ? 'success' : 'warning'} showIcon title={`完成 ${analyze.data.results.length} 条，其中 ${analyze.data.results.filter((x) => x.error !== null).length} 条失败`} />}
      </Card>
      <Card title="待分析消息">
        <QueryState loading={messages.isLoading} error={messages.error} empty={!messages.data?.items.length}>
          <Table<MessageItem> rowKey="id" rowSelection={{ selectedRowKeys: selected, onChange: (keys) => setSelected(keys.map(Number)) }} dataSource={messages.data?.items ?? []} pagination={false} columns={[
            { title: 'ID', dataIndex: 'id', width: 70 }, { title: '内容', dataIndex: 'content', ellipsis: true },
            { title: '状态', dataIndex: 'process_status' }, { title: '发送时间', dataIndex: 'sent_at', render: shanghai },
          ]} />
        </QueryState>
      </Card>
    </div>
  )
}




