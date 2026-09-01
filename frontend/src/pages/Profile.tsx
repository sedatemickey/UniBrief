import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button, Card, Form, Input, Typography } from 'antd'
import { authApi } from '../api'

export function ProfilePage() {
  const queryClient = useQueryClient()
  const change = useMutation({ mutationFn: authApi.changePassword, onSuccess: async () => await queryClient.invalidateQueries() })
  return (
    <Card title="个人资料与密码">
      <Form layout="vertical" onFinish={(values) => change.mutate(values)} className="narrow-form">
        {change.isSuccess && <Typography.Text type="success">密码已修改，请使用新密码重新登录。</Typography.Text>}
        {change.isError && <Typography.Text type="danger">{change.error instanceof Error ? change.error.message : '修改失败'}</Typography.Text>}
        <Form.Item name="current_password" label="当前密码" rules={[{ required: true }]}><Input.Password /></Form.Item>
        <Form.Item name="new_password" label="新密码" rules={[{ required: true }, { min: 10 }]}><Input.Password /></Form.Item>
        <Button type="primary" htmlType="submit" loading={change.isPending}>修改密码</Button>
      </Form>
    </Card>
  )
}

