import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Card, Form, Input, InputNumber, Modal, Select, Table, Tabs } from 'antd'
import { useState } from 'react'
import { dictionaryApi, sourceApi } from '../api'
import { QueryState } from '../components/QueryState'
import type { Channel, Sender } from '../api/types'
import { shanghai } from '../utils/format'

export function SourcesPage() {
  const queryClient = useQueryClient()
  const platforms = useQuery({ queryKey: ['platforms'], queryFn: dictionaryApi.platforms })
  const channels = useQuery({ queryKey: ['channels'], queryFn: () => sourceApi.channels({ page_size: 100 }) })
  const senders = useQuery({ queryKey: ['senders'], queryFn: () => sourceApi.senders({ page_size: 100 }) })
  const channelForm = Form.useForm<{ platform_id: number; external_id: string; name: string; channel_type: string }>()[0]
  const senderForm = Form.useForm<{ platform_id: number; external_id: string; display_name: string; source_type: string; credibility: number }>()[0]
  const [channelOpen, setChannelOpen] = useState(false)
  const [senderOpen, setSenderOpen] = useState(false)
  const createChannel = useMutation({ mutationFn: sourceApi.createChannel, onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['channels'] }); setChannelOpen(false) } })
  const createSender = useMutation({ mutationFn: sourceApi.createSender, onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['senders'] }); setSenderOpen(false) } })
  return (
    <Card title="消息来源管理">
      <Tabs items={[
        { key: 'channels', label: '渠道', children: (
          <>
            <Button type="primary" style={{ marginBottom: 16 }} onClick={() => setChannelOpen(true)}>新建渠道</Button>
            <QueryState loading={channels.isLoading} error={channels.error} empty={!channels.data?.items.length}>
              <Table<Channel> rowKey="id" dataSource={channels.data?.items ?? []} pagination={false} columns={[
                { title: '名称', dataIndex: 'name' }, { title: '类型', dataIndex: 'channel_type' },
                { title: '外部 ID', dataIndex: 'external_id' }, { title: '创建时间', dataIndex: 'created_at', render: shanghai },
              ]} />
            </QueryState>
          </>
        ) },
        { key: 'senders', label: '发送者', children: (
          <>
            <Button type="primary" style={{ marginBottom: 16 }} onClick={() => setSenderOpen(true)}>新建发送者</Button>
            <QueryState loading={senders.isLoading} error={senders.error} empty={!senders.data?.items.length}>
              <Table<Sender> rowKey="id" dataSource={senders.data?.items ?? []} pagination={false} columns={[
                { title: '名称', dataIndex: 'display_name' }, { title: '来源类型', dataIndex: 'source_type' },
                { title: '可信度', dataIndex: 'credibility' }, { title: '外部 ID', dataIndex: 'external_id' },
                { title: '创建时间', dataIndex: 'created_at', render: shanghai },
              ]} />
            </QueryState>
          </>
        ) },
      ]} />
      <Modal title="新建渠道" open={channelOpen} onCancel={() => setChannelOpen(false)} onOk={() => channelForm.submit()} confirmLoading={createChannel.isPending}>
        <Form form={channelForm} layout="vertical" onFinish={(values) => createChannel.mutate(values)}>
          <Form.Item name="platform_id" label="平台" rules={[{ required: true }]}><Select options={platforms.data?.items.map((x) => ({ value: x.id, label: `${x.name} / ${x.type}` }))} /></Form.Item>
          <Form.Item name="external_id" label="外部 ID" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="channel_type" label="类型" rules={[{ required: true }]}><Select options={[{ value: 'GROUP' }, { value: 'PRIVATE' }, { value: 'SYSTEM' }]} /></Form.Item>
        </Form>
      </Modal>
      <Modal title="新建发送者" open={senderOpen} onCancel={() => setSenderOpen(false)} onOk={() => senderForm.submit()} confirmLoading={createSender.isPending}>
        <Form form={senderForm} layout="vertical" onFinish={(values) => createSender.mutate(values)}>
          <Form.Item name="platform_id" label="平台" rules={[{ required: true }]}><Select options={platforms.data?.items.map((x) => ({ value: x.id, label: `${x.name} / ${x.type}` }))} /></Form.Item>
          <Form.Item name="external_id" label="外部 ID" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="display_name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="source_type" label="来源类型" initialValue="UNKNOWN"><Select options={['UNKNOWN', 'TEACHER', 'STUDENT', 'CLASS_LEADER', 'ADMIN'].map((x) => ({ value: x }))} /></Form.Item>
          <Form.Item name="credibility" label="可信度" initialValue={0.5}><InputNumber min={0} max={1} step={0.01} /></Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}

