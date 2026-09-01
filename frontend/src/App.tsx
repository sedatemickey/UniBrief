import {
  AimOutlined, BellOutlined, CalendarOutlined, DashboardOutlined, DatabaseOutlined,
  ImportOutlined, LineChartOutlined, RobotOutlined, TeamOutlined, UserOutlined,
} from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Layout, Menu, Space, Spin, Typography } from 'antd'
import type { ReactNode } from 'react'
import { Navigate, NavLink, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { adminApi, authApi } from './api'
import { AISettingsPage } from './pages/AISettings'
import { AdminPage } from './pages/Admin'
import { CalendarPage, RemindersPage } from './pages/Calendar'
import { DashboardPage, StatisticsPage } from './pages/Dashboard'
import { ImportAnalyzePage } from './pages/ImportAnalyze'
import { InformationDetailPage, InformationPage } from './pages/Information'
import { AdminLoginPage, LoginPage } from './pages/Login'
import { MessageDetailPage, MessagesPage } from './pages/Messages'
import { ProfilePage } from './pages/Profile'
import { SourcesPage } from './pages/Sources'
import { useModel } from './hooks/useModel'
import './styles.css'

const { Header, Sider, Content, Footer } = Layout

function UserShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const me = useQuery({ queryKey: ['me'], queryFn: authApi.me, retry: false })
  const logout = useMutation({
    mutationFn: authApi.logout,
    onSuccess: async () => { await queryClient.clear(); navigate('/login') },
  })
  if (me.isLoading) return <div className="full-loading"><Spin description="正在校验登录状态…" /></div>
  if (me.isError) return <Navigate to="/login" replace />
  return (
    <Layout className="app-shell">
      <Header className="app-header">
        <Space>
          <div className="brand-mark">U</div>
          <span className="brand-name">UniBrief</span>
        </Space>
        <Space>
          <Typography.Text>{me.data?.display_name}</Typography.Text>
          <Button size="small" onClick={() => logout.mutate()} loading={logout.isPending}>退出</Button>
        </Space>
      </Header>
      <Layout>
        <Sider width={216} className="app-sider">
          <Menu mode="inline" items={[
            { key: '/', icon: <DashboardOutlined />, label: <NavLink to="/">Dashboard</NavLink> },
            { key: '/information', icon: <AimOutlined />, label: <NavLink to="/information">有效信息</NavLink> },
            { key: '/messages', icon: <DatabaseOutlined />, label: <NavLink to="/messages">原始消息</NavLink> },
            { key: '/sources', icon: <TeamOutlined />, label: <NavLink to="/sources">消息来源</NavLink> },
            { key: '/import', icon: <ImportOutlined />, label: <NavLink to="/import">导入分析</NavLink> },
            { key: '/ai', icon: <RobotOutlined />, label: <NavLink to="/ai">AI 设置</NavLink> },
            { key: '/statistics', icon: <LineChartOutlined />, label: <NavLink to="/statistics">统计</NavLink> },
            { key: '/calendar', icon: <CalendarOutlined />, label: <NavLink to="/calendar">事项日历</NavLink> },
            { key: '/reminders', icon: <BellOutlined />, label: <NavLink to="/reminders">提醒中心</NavLink> },
            { key: '/profile', icon: <UserOutlined />, label: <NavLink to="/profile">个人资料</NavLink> },
          ]} />
        </Sider>
        <Content className="app-content">{children}</Content>
      </Layout>
      <Footer className="app-footer">UniBrief · 数据库课程设计</Footer>
    </Layout>
  )
}

function AdminShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const me = useQuery({ queryKey: ['admin-me'], queryFn: adminApi.me, retry: false })
  const logout = useMutation({ mutationFn: adminApi.logout, onSuccess: async () => { await queryClient.clear(); navigate('/admin/login') } })
  if (me.isLoading) return <div className="full-loading"><Spin description="正在校验管理员状态…" /></div>
  if (me.isError) return <Navigate to="/admin/login" replace />
  return (
    <Layout className="app-shell">
      <Header className="app-header">
        <Space><div className="brand-mark">A</div><span className="brand-name">UniBrief 管理端</span></Space>
        <Button size="small" onClick={() => logout.mutate()}>退出管理员</Button>
      </Header>
      <Content className="app-content">{children}</Content>
    </Layout>
  )
}

function UserRoute({ children }: { children: ReactNode }) { return <UserShell>{children}</UserShell> }

export default function App() {
  const { model } = useModel()
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/admin/login" element={<AdminLoginPage />} />
      <Route path="/admin" element={<AdminShell><AdminPage /></AdminShell>} />
      <Route path="/" element={<UserRoute><DashboardPage /></UserRoute>} />
      <Route path="/information" element={<UserRoute><InformationPage /></UserRoute>} />
      <Route path="/information/:id" element={<UserRoute><InformationIdRoute /></UserRoute>} />
      <Route path="/messages" element={<UserRoute><MessagesPage /></UserRoute>} />
      <Route path="/messages/:id" element={<UserRoute><MessageIdRoute model={model} /></UserRoute>} />
      <Route path="/sources" element={<UserRoute><SourcesPage /></UserRoute>} />
      <Route path="/import" element={<UserRoute><ImportAnalyzePage /></UserRoute>} />
      <Route path="/ai" element={<UserRoute><AISettingsPage /></UserRoute>} />
      <Route path="/statistics" element={<UserRoute><StatisticsPage /></UserRoute>} />
      <Route path="/calendar" element={<UserRoute><CalendarPage /></UserRoute>} />
      <Route path="/reminders" element={<UserRoute><RemindersPage /></UserRoute>} />
      <Route path="/profile" element={<UserRoute><ProfilePage /></UserRoute>} />
      <Route path="*" element={<div className="full-loading"><Alert type="warning" title="页面不存在" /></div>} />
    </Routes>
  )
}

function InformationIdRoute() { return <InformationDetailPage id={Number(useParams().id)} /> }
function MessageIdRoute({ model }: { model: string | null }) { return <MessageDetailPage id={Number(useParams().id)} model={model} /> }



