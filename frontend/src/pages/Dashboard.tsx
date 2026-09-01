import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Card, Col, Row, Statistic } from 'antd'
import { adminApi, statisticsApi } from '../api'
import { EChart } from '../components/EChart'
import { QueryState } from '../components/QueryState'

function range(): { start: string; end: string } {
  const end = new Date()
  const start = new Date(end.getTime() - 29 * 86400_000)
  return { start: start.toISOString(), end: end.toISOString() }
}

export function DashboardPage() {
  const time = useMemo(range, [])
  const overview = useQuery({ queryKey: ['statistics', 'overview', time], queryFn: () => statisticsApi.overview(time) })
  const channels = useQuery({ queryKey: ['statistics', 'channels', time], queryFn: () => statisticsApi.channels(time) })
  const categories = useQuery({ queryKey: ['statistics', 'categories', time], queryFn: () => statisticsApi.categories({ ...time, include_archived: false }) })
  const upcoming = useQuery({ queryKey: ['statistics', 'upcoming', 14], queryFn: () => statisticsApi.upcoming({ days: 14 }) })
  return (
    <div className="page-stack">
      <Row gutter={[16, 16]}>
        {overview.data ? [
          { title: '消息总数', value: overview.data.message_total },
          { title: '有效信息', value: overview.data.information_active_total },
          { title: '未来事项', value: overview.data.event_upcoming_total },
          { title: '到期提醒', value: overview.data.reminder_due_total },
        ].map((item) => (
          <Col xs={12} md={6} key={item.title}><Card><Statistic title={item.title} value={item.value} /></Card></Col>
        )) : null}
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="渠道消息有效率">
            <QueryState loading={channels.isLoading} error={channels.error} empty={!channels.data?.length}>
              <EChart height={320} option={{
                xAxis: { type: 'category', data: channels.data?.map((item) => item.channel_name) ?? [] },
                yAxis: { type: 'value', max: 1 },
                series: [{ type: 'bar', name: '有效率', data: channels.data?.map((item) => item.effectiveness_rate) ?? [] }],
                tooltip: { trigger: 'axis' },
              }} />
            </QueryState>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="信息分类分布">
            <QueryState loading={categories.isLoading} error={categories.error} empty={!categories.data?.length}>
              <EChart height={320} option={{
                tooltip: { trigger: 'item' },
                series: [{ type: 'pie', radius: ['38%', '68%'], data: categories.data?.map((item) => ({ name: item.category_name, value: item.information_count })) ?? [] }],
              }} />
            </QueryState>
          </Card>
        </Col>
      </Row>
      <Card title="未来 14 天事项">
        <QueryState loading={upcoming.isLoading} error={upcoming.error} empty={!upcoming.data?.total}>
          <EChart height={280} option={{
            xAxis: { type: 'category', data: upcoming.data?.by_date.map((item) => item.date.slice(5)) ?? [] },
            yAxis: { type: 'value' },
            series: [{ type: 'line', smooth: true, areaStyle: {}, data: upcoming.data?.by_date.map((item) => item.count) ?? [] }],
          }} />
        </QueryState>
      </Card>
    </div>
  )
}

export function StatisticsPage() {
  const time = useMemo(range, [])
  const channels = useQuery({ queryKey: ['statistics', 'channels', time], queryFn: () => statisticsApi.channels(time) })
  const categories = useQuery({ queryKey: ['statistics', 'categories', time], queryFn: () => statisticsApi.categories({ ...time, include_archived: false }) })
  const tags = useQuery({ queryKey: ['statistics', 'tags', time], queryFn: () => statisticsApi.tags({ ...time, limit: 20, include_archived: false }) })
  const upcoming = useQuery({ queryKey: ['statistics', 'upcoming', 30], queryFn: () => statisticsApi.upcoming({ days: 30 }) })
  return (
    <div className="page-stack">
      <Card title="渠道消息与有效率">
        <QueryState loading={channels.isLoading} error={channels.error} empty={!channels.data?.length}>
          <EChart height={360} option={{
            legend: { bottom: 0 },
            tooltip: { trigger: 'axis' },
            xAxis: { type: 'category', data: channels.data?.map((item) => item.channel_name) ?? [] },
            yAxis: [{ type: 'value' }, { type: 'value', max: 1 }],
            series: [
              { name: '消息数', type: 'bar', data: channels.data?.map((item) => item.message_count) ?? [] },
              { name: '有效消息', type: 'bar', data: channels.data?.map((item) => item.effective_message_count) ?? [] },
              { name: '有效率', type: 'line', yAxisIndex: 1, data: channels.data?.map((item) => item.effectiveness_rate) ?? [] },
            ],
          }} />
        </QueryState>
      </Card>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}><Card title="分类分布"><QueryState loading={categories.isLoading} error={categories.error} empty={!categories.data?.length}><EChart option={{ tooltip: { trigger: 'item' }, series: [{ type: 'pie', data: categories.data?.map((x) => ({ name: x.category_name, value: x.information_count })) ?? [] }] }} /></QueryState></Card></Col>
        <Col xs={24} lg={12}><Card title="热门标签"><QueryState loading={tags.isLoading} error={tags.error} empty={!tags.data?.length}><EChart option={{ grid: { left: 100 }, xAxis: { type: 'value' }, yAxis: { type: 'category', data: tags.data?.map((x) => x.tag_name).reverse() ?? [] }, series: [{ type: 'bar', data: tags.data?.map((x) => x.usage_count).reverse() ?? [] }] }} /></QueryState></Card></Col>
      </Row>
      <Card title="未来 30 天事项"><QueryState loading={upcoming.isLoading} error={upcoming.error} empty={!upcoming.data?.total}><EChart height={320} option={{ xAxis: { type: 'category', data: upcoming.data?.by_date.map((x) => x.date.slice(5)) ?? [] }, yAxis: { type: 'value' }, series: [{ type: 'bar', data: upcoming.data?.by_date.map((x) => x.count) ?? [] }] }} /></QueryState></Card>
    </div>
  )
}

export function AdminStatusPage() {
  const settings = useQuery({ queryKey: ['admin-settings'], queryFn: adminApi.settings })
  return <Card title="系统状态"><QueryState loading={settings.isLoading} error={settings.error}>{settings.data && (
    <Row><Col span={12}><Statistic title="注册开关" value={settings.data.registration_enabled ? '开启' : '关闭'} /></Col><Col span={12}><Statistic title="管理员密码" value={settings.data.admin_password_configured ? '已配置' : '未配置'} /></Col></Row>
  )}</QueryState></Card>
}

