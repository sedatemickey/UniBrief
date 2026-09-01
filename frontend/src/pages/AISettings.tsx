import { useMutation, useQuery } from '@tanstack/react-query'
import { Alert, Button, Card, Form, Input, Select, Space, Typography } from 'antd'
import { aiApi } from '../api'
import { QueryState } from '../components/QueryState'
import { useAIDefault, useModel } from '../hooks/useModel'

export function AISettingsPage() {
  const config = useAIDefault()
  const { model, setModel } = useModel()
  const models = useQuery({ queryKey: ['ai-models'], queryFn: aiApi.models })
  const test = useMutation({ mutationFn: aiApi.test })
  const selected = model ?? config.data?.default_model ?? ''
  return (
    <div className="page-stack">
      <Card title="AI 服务配置">
        <QueryState loading={config.isLoading} error={config.error}>
          <Typography.Paragraph>Base URL：<Typography.Text code>{config.data?.base_url}</Typography.Text></Typography.Paragraph>
          <Typography.Paragraph>API Key：<Typography.Text type={config.data?.has_api_key ? 'success' : 'danger'}>{config.data?.has_api_key ? '已配置' : '未配置'}</Typography.Text></Typography.Paragraph>
          <Typography.Paragraph>默认模型：<Typography.Text code>{config.data?.default_model || '未配置'}</Typography.Text></Typography.Paragraph>
        </QueryState>
      </Card>
      <Card title="模型选择与连接测试">
        <Space orientation="vertical" style={{ width: '100%' }} size="large">
          <Button onClick={() => models.refetch()} loading={models.isRefetching}>加载模型列表</Button>
          {models.data && !models.data.supports_listing && <Alert type="warning" showIcon title={models.data.message ?? '当前服务不支持模型列表，请手工输入模型 ID'} />}
          <Form layout="vertical">
            <Form.Item label="模型 ID">
              <Space.Compact style={{ width: '100%' }}>
                <Select style={{ width: '60%' }} value={selected || undefined} showSearch allowClear placeholder="选择模型" loading={models.isLoading} options={models.data?.models.map((item) => ({ value: item.id, label: item.id })) ?? []} onChange={setModel} />
                <Input style={{ width: '40%' }} value={selected} placeholder="手工输入模型 ID" onChange={(event) => setModel(event.target.value)} />
              </Space.Compact>
            </Form.Item>
            <Button type="primary" disabled={!selected} loading={test.isPending} onClick={() => selected && test.mutate(selected)}>测试连接（会产生真实请求）</Button>
          </Form>
          {test.isSuccess && <Alert type="success" showIcon title={test.data.message} description={`模型：${test.data.model}；耗时：${test.data.latency_ms} ms`} />}
          {test.isError && <Alert type="error" showIcon title={test.error instanceof Error ? test.error.message : '连接失败'} />}
        </Space>
      </Card>
    </div>
  )
}



