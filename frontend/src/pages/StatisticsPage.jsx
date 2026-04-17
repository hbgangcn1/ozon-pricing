import { useCallback, useEffect, useMemo, useState } from 'react'
import { Download, RefreshCw, Search, TrendingUp, Users, DollarSign, Activity, Target } from 'lucide-react'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/table'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Badge } from '../components/ui/badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs'
import { Progress } from '../components/ui/progress'
import { statisticsAPI } from '../services/api'

function StatisticCard({ title, value, suffix = '', icon: Icon, trend = null }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-text-secondary">{title}</p>
            <div className="text-2xl font-bold text-text-primary mt-1 font-headline tracking-tight">
              {value}{suffix && <span className="text-sm font-normal text-text-secondary ml-1">{suffix}</span>}
            </div>
            {trend && (
              <p className="text-sm text-text-secondary mt-1">{trend}</p>
            )}
          </div>
          {Icon && (
            <div className="h-12 w-12 rounded-full bg-surface-container flex items-center justify-center">
              <Icon className="h-6 w-6 text-text-secondary" />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

const PAGE_SIZE = 20
const SEARCH_DEBOUNCE_MS = 300

const emptyPage = {
  items: [],
  total: 0,
  page: 1,
  page_size: PAGE_SIZE,
}

function buildCsv(rows, headers) {
  const escapeCell = (value) => {
    const normalized = String(value ?? '')
    return `"${normalized.replaceAll('"', '""')}"`
  }

  return [
    headers.map(({ label }) => escapeCell(label)).join(','),
    ...rows.map((row) => headers.map(({ key }) => escapeCell(row[key])).join(',')),
  ].join('\n')
}

function downloadCsv(filename, content) {
  const blob = new Blob([`\ufeff${content}`], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function PaginationControls({ page, pageSize, total, onPageChange }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize) || 1)

  return (
    <div className="flex gap-2">
      <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
        上一页
      </Button>
      <Button variant="outline" size="sm" disabled>
        {page} / {totalPages}
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        下一页
      </Button>
    </div>
  )
}

function StatisticsPage() {
  const [activeTab, setActiveTab] = useState('overview')
  const [statsData, setStatsData] = useState(null)
  const [retentionData, setRetentionData] = useState([])
  const [loginLogsPage, setLoginLogsPage] = useState(emptyPage)
  const [adminLogsPage, setAdminLogsPage] = useState(emptyPage)
  const [revenueData, setRevenueData] = useState([])
  const [activeData, setActiveData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loginPage, setLoginPage] = useState(1)
  const [adminPage, setAdminPage] = useState(1)
  const [loginSearchInput, setLoginSearchInput] = useState('')
  const [adminSearchInput, setAdminSearchInput] = useState('')
  const [loginSearch, setLoginSearch] = useState('')
  const [adminSearch, setAdminSearch] = useState('')
  const [loginDateFrom, setLoginDateFrom] = useState('')
  const [loginDateTo, setLoginDateTo] = useState('')
  const [adminDateFrom, setAdminDateFrom] = useState('')
  const [adminDateTo, setAdminDateTo] = useState('')

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setLoginSearch(loginSearchInput.trim())
      setLoginPage(1)
    }, SEARCH_DEBOUNCE_MS)

    return () => window.clearTimeout(timer)
  }, [loginSearchInput])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setAdminSearch(adminSearchInput.trim())
      setAdminPage(1)
    }, SEARCH_DEBOUNCE_MS)

    return () => window.clearTimeout(timer)
  }, [adminSearchInput])

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [overviewRes, retentionRes, revenueRes, loginRes, adminRes, activeRes] = await Promise.all([
        statisticsAPI.getOverview(),
        statisticsAPI.getRetention(),
        statisticsAPI.getRevenue(),
        statisticsAPI.getLoginLogs(loginPage, PAGE_SIZE, loginSearch, loginDateFrom, loginDateTo),
        statisticsAPI.getAdminLogs(adminPage, PAGE_SIZE, adminSearch, adminDateFrom, adminDateTo),
        statisticsAPI.getActiveUsers(),
      ])

      setStatsData(overviewRes)
      setRetentionData(retentionRes)
      setRevenueData(revenueRes)
      setLoginLogsPage(loginRes)
      setAdminLogsPage(adminRes)
      setActiveData(activeRes)
    } catch (err) {
      console.error('Failed to fetch statistics:', err)
    } finally {
      setLoading(false)
    }
  }, [adminDateFrom, adminDateTo, adminPage, adminSearch, loginDateFrom, loginDateTo, loginPage, loginSearch])

  useEffect(() => {
    void fetchData()
  }, [fetchData])

  const loginLogs = useMemo(() => loginLogsPage.items ?? [], [loginLogsPage.items])
  const adminLogs = useMemo(() => adminLogsPage.items ?? [], [adminLogsPage.items])

  const handleLoginExport = useCallback(() => {
    downloadCsv(
      `login-logs-page-${loginLogsPage.page}.csv`,
      buildCsv(loginLogs, [
        { key: 'id', label: 'ID' },
        { key: 'username', label: '用户名' },
        { key: 'action', label: '操作' },
        { key: 'ip', label: 'IP地址' },
        { key: 'time', label: '时间' },
        { key: 'status', label: '状态' },
      ])
    )
  }, [loginLogs, loginLogsPage.page])

  const handleAdminExport = useCallback(() => {
    downloadCsv(
      `admin-logs-page-${adminLogsPage.page}.csv`,
      buildCsv(adminLogs, [
        { key: 'id', label: 'ID' },
        { key: 'admin', label: '管理员' },
        { key: 'action', label: '操作内容' },
        { key: 'time', label: '时间' },
      ])
    )
  }, [adminLogs, adminLogsPage.page])

  const totalPaidUsers = useMemo(
    () => (statsData?.pro_users ?? 0) + (statsData?.eff_users ?? 0),
    [statsData]
  )

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-text-primary font-headline tracking-tight">
        数据统计 — 系统数据统计与分析
      </h1>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">总览</TabsTrigger>
          <TabsTrigger value="retention">留存分析</TabsTrigger>
          <TabsTrigger value="active">用户活跃</TabsTrigger>
          <TabsTrigger value="revenue">充值与收入</TabsTrigger>
          <TabsTrigger value="logs">操作日志</TabsTrigger>
          <TabsTrigger value="loginLogs">登录记录</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatisticCard title="总用户数" value={statsData?.total_users ?? 0} icon={Users} />
            <StatisticCard title="活跃用户" value={statsData?.active_users ?? 0} icon={Activity} />
            <StatisticCard title="今日新增" value={statsData?.new_users_today ?? 0} icon={TrendingUp} />
            <StatisticCard title="总收入" value={statsData?.total_revenue ?? 0} suffix="¥" icon={DollarSign} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatisticCard title="专业版用户" value={statsData?.pro_users ?? 0} suffix="人" icon={Target} />
            <StatisticCard title="效率版用户" value={statsData?.eff_users ?? 0} suffix="人" icon={Target} />
            <StatisticCard title="免费版用户" value={statsData?.free_users ?? 0} suffix="人" icon={Target} />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>用户留存趋势</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {retentionData.map((d) => (
                  <div key={d.month} className="bg-surface-container rounded-lg border border-surface-high p-4">
                    <p className="text-sm text-text-secondary">{d.month}</p>
                    <div className="text-2xl font-bold text-text-primary mt-1 font-headline tracking-tight">
                      {d.retention}%
                    </div>
                    <Progress value={d.retention} className="mt-2" />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="retention">
          <Card>
            <CardHeader>
              <CardTitle>用户留存率分析</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="bg-surface-high/30 border border-surface-highest/50 rounded-lg p-4 mb-4">
                <p className="text-sm text-text-secondary">
                  留存分析数据基于用户月度活跃情况统计
                </p>
              </div>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>月份</TableHead>
                    <TableHead>留存率(%)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {retentionData.map((d) => (
                    <TableRow key={d.month}>
                      <TableCell className="font-medium">{d.month}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Progress value={d.retention} className="flex-1" />
                          <span className="text-sm font-medium">{d.retention}%</span>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="active">
          <Card>
            <CardHeader>
              <CardTitle>用户活跃统计</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card className="bg-surface border-surface-high">
                  <CardHeader>
                    <CardTitle className="text-lg">日活趋势</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <StatisticCard title="今日活跃" value={activeData?.daily ?? 0} icon={Users} />
                    <p className="text-sm text-text-secondary mt-2">较昨日 {activeData?.trend_daily ?? 'N/A'}</p>
                  </CardContent>
                </Card>

                <Card className="bg-surface border-surface-high">
                  <CardHeader>
                    <CardTitle className="text-lg">周活趋势</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <StatisticCard title="本周活跃" value={activeData?.weekly ?? 0} icon={Users} />
                    <p className="text-sm text-text-secondary mt-2">较上周 {activeData?.trend_weekly ?? 'N/A'}</p>
                  </CardContent>
                </Card>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="revenue" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatisticCard title="本月收入" value={revenueData[revenueData.length - 1]?.revenue ?? 0} suffix="¥" icon={DollarSign} />
            <StatisticCard title="累计收入" value={statsData?.total_revenue ?? 0} suffix="¥" icon={DollarSign} />
            <StatisticCard title="付费用户" value={totalPaidUsers} suffix="人" icon={Users} />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>月度收入趋势</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {revenueData.map((d) => (
                  <Card key={d.month} className="bg-surface border-surface-high">
                    <CardContent className="pt-4">
                      <p className="text-sm text-text-secondary">{d.month}</p>
                      <div className="text-2xl font-bold text-text-primary mt-1 font-headline tracking-tight">
                        ¥{d.revenue}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="logs">
          <Card>
            <CardHeader>
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <CardTitle>管理员操作日志</CardTitle>
                <div className="flex flex-col md:flex-row gap-2">
                  <div className="relative w-full md:w-64">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
                    <Input
                      placeholder="搜索"
                      className="pl-10 transition-all duration-200"
                      value={adminSearchInput}
                      onChange={(e) => setAdminSearchInput(e.target.value)}
                    />
                  </div>
                  <Input type="date" value={adminDateFrom} onChange={(e) => { setAdminDateFrom(e.target.value); setAdminPage(1) }} />
                  <Input type="date" value={adminDateTo} onChange={(e) => { setAdminDateTo(e.target.value); setAdminPage(1) }} />
                  <Button variant="outline" onClick={handleAdminExport} disabled={!adminLogs.length}>
                    <Download className="w-4 h-4 mr-2" />
                    导出
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16">ID</TableHead>
                    <TableHead className="w-32">管理员</TableHead>
                    <TableHead>操作内容</TableHead>
                    <TableHead className="w-48">时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {adminLogs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell className="font-medium">{log.id}</TableCell>
                      <TableCell>{log.admin}</TableCell>
                      <TableCell>{log.action}</TableCell>
                      <TableCell className="text-text-secondary">{log.time}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <div className="flex items-center justify-between mt-4 pt-4 border-t border-surface-high">
                <p className="text-sm text-text-secondary">共 {adminLogsPage.total} 条</p>
                <PaginationControls
                  page={adminLogsPage.page}
                  pageSize={adminLogsPage.page_size}
                  total={adminLogsPage.total}
                  onPageChange={setAdminPage}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="loginLogs">
          <Card>
            <CardHeader>
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <CardTitle>用户登录记录</CardTitle>
                <div className="flex flex-col md:flex-row gap-2">
                  <div className="relative w-full md:w-48">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
                    <Input
                      placeholder="搜索用户"
                      className="pl-10 transition-all duration-200"
                      value={loginSearchInput}
                      onChange={(e) => setLoginSearchInput(e.target.value)}
                    />
                  </div>
                  <Input type="date" value={loginDateFrom} onChange={(e) => { setLoginDateFrom(e.target.value); setLoginPage(1) }} />
                  <Input type="date" value={loginDateTo} onChange={(e) => { setLoginDateTo(e.target.value); setLoginPage(1) }} />
                  <Button variant="outline" onClick={handleLoginExport} disabled={!loginLogs.length}>
                    <Download className="w-4 h-4 mr-2" />
                    导出登录记录
                  </Button>
                  <Button variant="outline" onClick={() => void fetchData()} disabled={loading}>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    刷新
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16">ID</TableHead>
                    <TableHead className="w-32">用户名</TableHead>
                    <TableHead className="w-32">操作</TableHead>
                    <TableHead className="w-32">IP地址</TableHead>
                    <TableHead className="w-48">时间</TableHead>
                    <TableHead className="w-20">状态</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loginLogs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell className="font-medium">{log.id}</TableCell>
                      <TableCell>{log.username}</TableCell>
                      <TableCell>{log.action}</TableCell>
                      <TableCell className="text-text-secondary">{log.ip}</TableCell>
                      <TableCell className="text-text-secondary">{log.time}</TableCell>
                      <TableCell>
                        <Badge variant={log.status === '成功' ? 'default' : 'destructive'}>
                          {log.status}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <div className="flex items-center justify-between mt-4 pt-4 border-t border-surface-high">
                <p className="text-sm text-text-secondary">共 {loginLogsPage.total} 条</p>
                <PaginationControls
                  page={loginLogsPage.page}
                  pageSize={loginLogsPage.page_size}
                  total={loginLogsPage.total}
                  onPageChange={setLoginPage}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default StatisticsPage
