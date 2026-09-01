import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, Card, Form, Input, Modal, Space, Switch, Table, Tabs, Typography } from 'antd'
import { useState } from 'react'
import { adminApi } from '../api'
import { ApiError } from '../api/client'
import { QueryState } from '../components/QueryState'
import type { Category, Platform, User } from '../api/types'
import { shanghai } from '../utils/format'

export function AdminPage() {
  const queryClient = useQueryClient()
  const users = useQuery({ queryKey: ['admin-users'], queryFn: () => adminApi.users({ page: 1, page_size: 100 }) })
  const platforms = useQuery({ queryKey: ['admin-platforms'], queryFn: () => adminApi.platforms({ page_size: 100 }) })
  const categories = useQuery({ queryKey: ['admin-categories'], queryFn: () => adminApi.categories({ page_size: 100 }) })
  const settings = useQuery({ queryKey: ['admin-settings'], queryFn: adminApi.settings })
  const [userOpen, setUserOpen] = useState(false)
  const [platformOpen, setPlatformOpen] = useState(false)
  const [categoryOpen, setCategoryOpen] = useState(false)
  const [userForm] = Form.useForm()
  const [platformForm] = Form.useForm()
  const [categoryForm] = Form.useForm()
  const createUser = useMutation({ mutationFn: adminApi.createUser, onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['admin-users'] }); setUserOpen(false) } })
  const patchUser = useMutation({ mutationFn: ({ id, values }: { id: number; values: { status?: 'ACTIVE' | 'DISABLED' } }) => adminApi.patchUser(id, values), onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['admin-users'] }) })
  const reset = useMutation({ mutationFn: ({ id, password }: { id: number; password: string }) => adminApi.resetPassword(id, { new_password: password }), onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['admin-users'] }) })
  const registration = useMutation({ mutationFn: adminApi.registration, onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['admin-settings'] }) })
  const createPlatform = useMutation({ mutationFn: adminApi.createPlatform, onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['admin-platforms'] }); setPlatformOpen(false) } })
  const patchPlatform = useMutation({ mutationFn: ({ id, values }: { id: number; values: Record<string, unknown> }) => adminApi.patchPlatform(id, values), onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['admin-platforms'] }) })
  const createCategory = useMutation({ mutationFn: adminApi.createCategory, onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['admin-categories'] }); setCategoryOpen(false) } })
  const patchCategory = useMutation({ mutationFn: ({ id, values }: { id: number; values: Record<string, unknown> }) => adminApi.patchCategory(id, values), onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['admin-categories'] }) })
  const changePassword = useMutation({ mutationFn: adminApi.changePassword, onSuccess: async () => queryClient.invalidateQueries() })

  return (
    <div className="page-stack">
      <Card title="系统设置">
        <Space>注册开关 <Switch checked={settings.data?.registration_enabled} loading={settings.isLoading} onChange={(enabled: boolean) => registration.mutate({ enabled })} /></Space>
      </Card>
      <Card title="用户管理" extra={<Button type="primary" onClick={() => setUserOpen(true)}>创建用户</Button>}>
        <QueryState loading={users.isLoading} error={users.error} empty={!users.data?.items.length}>
          <Table<User> rowKey="id" dataSource={users.data?.items ?? []} columns={[
            { title: '用户名', dataIndex: 'username' }, { title: '显示名称', dataIndex: 'display_name' },
            { title: '状态', dataIndex: 'status', render: (value) => <Badge status={value === 'ACTIVE' ? 'success' : 'default'} text={value} /> },
            { title: '最后登录', dataIndex: 'last_login_at', render: shanghai },
            { title: '操作', render: (_, item) => (
              <Space>
                <Button size="small" onClick={() => patchUser.mutate({ id: item.id, values: { status: item.status === 'ACTIVE' ? 'DISABLED' : 'ACTIVE' } })}>{item.status === 'ACTIVE' ? '停用' : '启用'}</Button>
                <Button size="small" onClick={() => { const password = window.prompt('输入新密码（至少 10 位）'); if (password) reset.mutate({ id: item.id, password }) }}>重置密码</Button>
              </Space>
            )},
          ]} />
        </QueryState>
      </Card>
      <Card title="全局字典">
        <Tabs items={[
          { key: 'platforms', label: '平台', children: (
            <>
              <Button type="primary" style={{ marginBottom: 16 }} onClick={() => setPlatformOpen(true)}>新建平台</Button>
              <Table<Platform> rowKey="id" dataSource={platforms.data?.items ?? []} pagination={false} columns={[
                { title: '名称', dataIndex: 'name' }, { title: '类型', dataIndex: 'type' },
                { title: '状态', render: (_, item) => <Switch checked={item.status === 'ACTIVE'} onChange={(checked: boolean) => patchPlatform.mutate({ id: item.id, values: { status: checked ? 'ACTIVE' : 'DISABLED' } })} /> },
              ]} />
            </>
          ) },
          { key: 'categories', label: '分类', children: (
            <>
              <Button type="primary" style={{ marginBottom: 16 }} onClick={() => setCategoryOpen(true)}>新建分类</Button>
              <Table<Category> rowKey="id" dataSource={categories.data?.items ?? []} pagination={false} columns={[
                { title: '名称', dataIndex: 'name' }, { title: '描述', dataIndex: 'description', ellipsis: true },
                { title: '状态', render: (_, item) => <Switch checked={item.status === 'ACTIVE'} onChange={(checked: boolean) => patchCategory.mutate({ id: item.id, values: { status: checked ? 'ACTIVE' : 'DISABLED' } })} /> },
              ]} />
            </>
          ) },
        ]} />
      </Card>
      <Card title="修改管理员密码">
        <Form layout="vertical" className="narrow-form" onFinish={(values) => changePassword.mutate(values)}>
          {changePassword.isError && <Typography.Text type="danger">{changePassword.error instanceof ApiError ? changePassword.error.message : '修改失败'}</Typography.Text>}
          <Form.Item name="current_password" label="当前密码"><Input.Password /></Form.Item>
          <Form.Item name="new_password" label="新密码"><Input.Password /></Form.Item>
          <Button htmlType="submit" type="primary">修改</Button>
        </Form>
      </Card>
      <Modal title="创建用户" open={userOpen} onCancel={() => setUserOpen(false)} onOk={() => userForm.submit()} confirmLoading={createUser.isPending}>
        <Form form={userForm} layout="vertical" onFinish={(values) => createUser.mutate(values)}>
          <Form.Item name="username" label="用户名"><Input /></Form.Item>
          <Form.Item name="display_name" label="显示名称"><Input /></Form.Item>
          <Form.Item name="password" label="密码"><Input.Password /></Form.Item>
        </Form>
      </Modal>
      <Modal title="新建平台" open={platformOpen} onCancel={() => setPlatformOpen(false)} onOk={() => platformForm.submit()} confirmLoading={createPlatform.isPending}>
        <Form form={platformForm} layout="vertical" onFinish={(values) => createPlatform.mutate(values)}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="type" label="类型" rules={[{ required: true }]}><Input /></Form.Item>
        </Form>
      </Modal>
      <Modal title="新建分类" open={categoryOpen} onCancel={() => setCategoryOpen(false)} onOk={() => categoryForm.submit()} confirmLoading={createCategory.isPending}>
        <Form form={categoryForm} layout="vertical" onFinish={(values) => createCategory.mutate(values)}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="description" label="描述"><Input /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
