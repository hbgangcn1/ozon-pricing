import { useState } from 'react'
import { Download, RefreshCw, Search, TrendingUp, Users, DollarSign, Activity, AlertTriangle, Target } from 'lucide-react'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/table'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Badge } from '../components/ui/badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs'
import { Progress } from '../components/ui/progress'

// 模拟数据
const mockStatsData = {
  totalUsers: 42,
  activeUsers: 38,
  newUsersToday: 3,
  totalOrders: 156,
  totalRevenue: 12850,
  proUsers: 12,
  effUsers: 18,
  freeUsers: 12,
}

const mockRetentionData = [
  { month: '1月', retention: 95 },
  { month: '2月', retention: 88 },
  { month: '3月', retention: 82 },
]

const mockLoginLogs = [
  { id: 1, username: 'admin', action: '登录', ip: '192.168.1.1', time: '2026-03-22 20:46:40', status: '成功' },
  { id: 2, username: 'admin', action: '访问定价计算', ip: '192.168.1.1', time: '2026-03-22 20:47:00', status: '成功' },
  { id: 3, username: 'robert', action: '登录', ip: '192.168.1.2', time: '2026-03-22 19:30:15', status: '成功' },
  { id: 4, username: 'robert', action: '物流管理', ip: '192.168.1.2', time: '2026-03-22 19:31:00', status: '成功' },
  { id: 5, username: 'cbpriceprm0001', action: '登录', ip: '10.0.0.1', time: '2026-03-22 18:20:00', status: '成功' },
  { id: 6, username: 'cbpriceprm0002', action: '登录失败', ip: '10.0.0.2', time: '2026-03-22 17:15:00', status: '失败' },
  { id: 7, username: 'admin', action: '用户管理', ip: '192.168.1.1', time: '2026-03-22 16:00:00', status: '成功' },
  { id: 8, username: 'admin', action: '套餐管理', ip: '192.168.1.1', time: '2026-03-22 15:30:00', status: '成功' },
]

const mockAdminLogs = [
  { id: 1, admin: 'admin', action: '添加物流规则: China Post e邮宝', time: '2026-03-22 10:00:00' },
  { id: 2, admin: 'admin', action: '修改套餐价格: 专业版', time: '2026-03-21 15:30:00' },
  { id: 3, admin: 'admin', action: '删除用户: test_user', time: '2026-03-20 09:15:00' },
  { id: 4, admin: 'admin', action: '系统设置: 开启开放注册', time: '2026-03-19 14:20:00' },
  { id: 5, admin: 'admin', action: '备份数据库', time: '2026-03-19 02:00:00' },
]

const mockRevenueData = [
  { month: '1月', revenue: 3800 },
  { month: '2月', revenue: 5200 },
  { month: '3月', revenue: 3850 },
]

// 统计卡片组件
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

// Progress组件已从../components/ui/progress导入

function StatisticsPage() {
  const [activeTab, setActiveTab] = useState('overview')

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
          <TabsTrigger value="monitor">异常监控</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          {/* 主要统计卡片 */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatisticCard 
              title="总用户数" 
              value={mockStatsData.totalUsers} 
              icon={Users}
            />
            <StatisticCard 
              title="活跃用户" 
              value={mockStatsData.activeUsers} 
              icon={Activity}
            />
            <StatisticCard 
              title="今日新增" 
              value={mockStatsData.newUsersToday} 
              icon={TrendingUp}
            />
            <StatisticCard 
              title="总收入" 
              value={mockStatsData.totalRevenue} 
              suffix="¥"
              icon={DollarSign}
            />
          </div>

          {/* 套餐用户分布 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatisticCard 
              title="专业版用户" 
              value={mockStatsData.proUsers} 
              suffix="人"
              icon={Target}
            />
            <StatisticCard 
              title="效率版用户" 
              value={mockStatsData.effUsers} 
              suffix="人"
              icon={Target}
            />
            <StatisticCard 
              title="免费版用户" 
              value={mockStatsData.freeUsers} 
              suffix="人"
              icon={Target}
            />
          </div>

          {/* 用户留存趋势 */}
          <Card>
            <CardHeader>
              <CardTitle>用户留存趋势</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {mockRetentionData.map(d => (
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
                  {mockRetentionData.map((d, i) => (
                    <TableRow key={i}>
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
                    <StatisticCard title="今日活跃" value={38} icon={Users} />
                    <p className="text-sm text-text-secondary mt-2">较昨日 +5</p>
                  </CardContent>
                </Card>
                
                <Card className="bg-surface border-surface-high">
                  <CardHeader>
                    <CardTitle className="text-lg">周活趋势</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <StatisticCard title="本周活跃" value={42} icon={Users} />
                    <p className="text-sm text-text-secondary mt-2">较上周 +3</p>
                  </CardContent>
                </Card>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="revenue" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatisticCard 
              title="本月收入" 
              value={3850} 
              suffix="¥"
              icon={DollarSign}
            />
            <StatisticCard 
              title="累计收入" 
              value={12850} 
              suffix="¥"
              icon={DollarSign}
            />
            <StatisticCard 
              title="付费用户" 
              value={30} 
              suffix="人"
              icon={Users}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>月度收入趋势</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {mockRevenueData.map(d => (
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
                <div className="flex gap-2">
                  <div className="relative w-full md:w-64">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
                    <Input placeholder="搜索" className="pl-10 transition-all duration-200" />
                  </div>
                  <Button variant="outline">
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
                  {mockAdminLogs.map(log => (
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
                <p className="text-sm text-text-secondary">共 {mockAdminLogs.length} 条</p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled>上一页</Button>
                  <Button variant="outline" size="sm">1</Button>
                  <Button variant="outline" size="sm" disabled>下一页</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="loginLogs">
          <Card>
            <CardHeader>
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <CardTitle>用户登录记录</CardTitle>
                <div className="flex gap-2">
                  <div className="relative w-full md:w-48">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
                    <Input placeholder="搜索用户" className="pl-10 transition-all duration-200" />
                  </div>
                  <Button variant="outline">
                    <Download className="w-4 h-4 mr-2" />
                    导出登录记录
                  </Button>
                  <Button variant="outline">
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
                  {mockLoginLogs.map(log => (
                    <TableRow key={log.id}>
                      <TableCell className="font-medium">{log.id}</TableCell>
                      <TableCell>{log.username}</TableCell>
                      <TableCell>{log.action}</TableCell>
                      <TableCell className="text-text-secondary">{log.ip}</TableCell>
                      <TableCell className="text-text-secondary">{log.time}</TableCell>
                      <TableCell>
                        <Badge 
                          variant={log.status === '成功' ? 'default' : 'destructive'}
                        >
                          {log.status}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-surface-high">
                <p className="text-sm text-text-secondary">共 {mockLoginLogs.length} 条</p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled>上一页</Button>
                  <Button variant="outline" size="sm">1</Button>
                  <Button variant="outline" size="sm" disabled>下一页</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="monitor">
          <Card>
            <CardHeader>
              <CardTitle>系统异常告警</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="bg-green-900/30 border border-green-800/50 rounded-lg p-4">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-full bg-green-800 flex items-center justify-center">
                    <Activity className="h-4 w-4 text-status-success" />
                  </div>
                  <div>
                    <p className="text-green-200">暂无异常情况</p>
                    <p className="text-sm text-status-success/70">系统运行正常</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default StatisticsPage
