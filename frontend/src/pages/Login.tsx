import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Card, Form, Input, Tabs, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { adminApi, authApi } from '../api'
import { ApiError } from '../api/client'

export function LoginPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const status = useQuery({ queryKey: ['registration-status'], queryFn: authApi.registrationStatus })
  const login = useMutation({
    mutationFn: authApi.login,
    onSuccess: async () => { await queryClient.invalidateQueries(); navigate('/') },
  })
  const register = useMutation({
    mutationFn: authApi.register,
    onSuccess: async () => { await queryClient.invalidateQueries(); navigate('/') },
  })
  const errorMessage = (error: unknown) => error instanceof ApiError ? error.message : undefined
  return (
    <div className="auth-shell">
      <Card className="auth-card" title="UniBrief 登录" variant="borderless">
        <Typography.Paragraph type="secondary">普通用户私有消息与信息空间</Typography.Paragraph>
        <Tabs items={[
          { key: 'login', label: '登录', children: (
            <Form layout="vertical" onFinish={(values) => login.mutate(values)}>
              {login.isError && <Alert type="error" showIcon title={errorMessage(login.error)} />}
              <Form.Item name="username" label="用户名" rules={[{ required: true }]}><Input autoComplete="username" /></Form.Item>
              <Form.Item name="password" label="密码" rules={[{ required: true }]}><Input.Password autoComplete="current-password" /></Form.Item>
              <Button type="primary" htmlType="submit" block loading={login.isPending}>登录</Button>
            </Form>
          ) },
          ...(status.data?.enabled ? [{ key: 'register', label: '注册', children: (
            <Form layout="vertical" onFinish={(values) => register.mutate(values)}>
              {register.isError && <Alert type="error" showIcon title={errorMessage(register.error)} />}
              <Form.Item name="username" label="用户名" rules={[{ required: true }]}><Input /></Form.Item>
              <Form.Item name="display_name" label="显示名称" rules={[{ required: true }]}><Input /></Form.Item>
              <Form.Item name="password" label="密码" rules={[{ required: true }, { min: 10, message: '至少 10 位' }]}><Input.Password /></Form.Item>
              <Button type="primary" htmlType="submit" block loading={register.isPending}>创建账号</Button>
            </Form>
          ) }] : []),
        ]} />
        <Button type="link" onClick={() => navigate('/admin/login')}>管理员入口</Button>
      </Card>
    </div>
  )
}

export function AdminLoginPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const login = useMutation({
    mutationFn: adminApi.login,
    onSuccess: async () => { await queryClient.invalidateQueries(); navigate('/admin') },
  })
  return (
    <div className="auth-shell">
      <Card className="auth-card" title="管理员登录" variant="borderless">
        <Typography.Paragraph type="secondary">管理员只能维护账号、注册开关和全局字典。</Typography.Paragraph>
        <Form layout="vertical" onFinish={(values) => login.mutate(values)}>
          {login.isError && <Alert type="error" showIcon title={login.error instanceof ApiError ? login.error.message : '登录失败'} />}
          <Form.Item name="password" label="管理员密码" rules={[{ required: true }]}><Input.Password /></Form.Item>
          <Button type="primary" htmlType="submit" block loading={login.isPending}>登录管理员</Button>
        </Form>
      </Card>
    </div>
  )
}


