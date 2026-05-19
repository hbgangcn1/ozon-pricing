import React from 'react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'

const apiDefault = {
  get: vi.fn(),
}

const statisticsAPI = {
  getOverview: vi.fn(),
  getRetention: vi.fn(),
  getRevenue: vi.fn(),
  getLoginLogs: vi.fn(),
  getAdminLogs: vi.fn(),
  getActiveUsers: vi.fn(),
  getOrders: vi.fn(),
}

vi.mock('lucide-react', () => ({
  Download: () => null,
  RefreshCw: () => null,
  Search: () => null,
  TrendingUp: () => null,
  Users: () => null,
  DollarSign: () => null,
  Activity: () => null,
  Target: () => null,
}))

vi.mock('../services/api', () => ({
  default: apiDefault,
  statisticsAPI,
}))

vi.mock('../components/ui/card', () => ({
  Card: ({ children, className }) => <div className={className}>{children}</div>,
  CardHeader: ({ children, className }) => <div className={className}>{children}</div>,
  CardTitle: ({ children }) => <h2>{children}</h2>,
  CardContent: ({ children, className }) => <div className={className}>{children}</div>,
}))

vi.mock('../components/ui/button', () => ({
  Button: ({ children, onClick, disabled, className, type, ...props }) => (
    <button onClick={onClick} disabled={disabled} className={className} type={type} {...props}>
      {children}
    </button>
  ),
}))

vi.mock('../components/ui/input', () => ({
  Input: (props) => <input {...props} />,
}))

vi.mock('../components/ui/badge', () => ({
  Badge: ({ children, className }) => <span className={className}>{children}</span>,
}))

vi.mock('../components/ui/table', () => ({
  Table: ({ children }) => <table>{children}</table>,
  TableBody: ({ children }) => <tbody>{children}</tbody>,
  TableCell: ({ children, className }) => <td className={className}>{children}</td>,
  TableHead: ({ children, className }) => <th className={className}>{children}</th>,
  TableHeader: ({ children }) => <thead>{children}</thead>,
  TableRow: ({ children }) => <tr>{children}</tr>,
}))

vi.mock('../components/ui/tabs', () => {
  const ReactLocal = React
  const TabsContext = ReactLocal.createContext({ value: '', onValueChange: () => {} })

  return {
    Tabs: ({ children, value, onValueChange }) => (
      <TabsContext.Provider value={{ value, onValueChange }}>
        <div data-active={value}>{children}</div>
      </TabsContext.Provider>
    ),
    TabsList: ({ children }) => <div role="tablist">{children}</div>,
    TabsTrigger: ({ children, value }) => {
      const ctx = ReactLocal.useContext(TabsContext)
      return (
        <button type="button" role="tab" data-value={value} onClick={() => ctx.onValueChange(value)}>
          {children}
        </button>
      )
    },
    TabsContent: ({ children, value }) => {
      const ctx = ReactLocal.useContext(TabsContext)
      return ctx.value === value ? <div data-tab={value}>{children}</div> : null
    },
  }
})

vi.mock('../components/ui/progress', () => ({
  Progress: ({ value, className }) => <div className={className} data-progress={value} />,
}))

vi.mock('../components/ui/select', () => ({
  Select: ({ children, value, onValueChange }) => (
    <div data-select-value={value}>
      {children}
      <select data-testid="mock-select" value={value} onChange={(e) => onValueChange(e.target.value)}>
        <option value="all">全部</option>
        <option value="PENDING">PENDING</option>
        <option value="SUCCESS">SUCCESS</option>
        <option value="FAILED">FAILED</option>
      </select>
    </div>
  ),
  SelectTrigger: ({ children }) => <div>{children}</div>,
  SelectContent: ({ children }) => <div>{children}</div>,
  SelectItem: ({ children, value }) => <div data-value={value}>{children}</div>,
  SelectValue: ({ placeholder }) => <span>{placeholder}</span>,
}))

const overviewPayload = {
  total_users: 42,
  active_users: 18,
  new_users_today: 3,
  total_orders: 9,
  total_revenue: 1234.56,
  pro_users: 6,
  eff_users: 5,
  free_users: 31,
}

const retentionPayload = [
  { month: '2026-01', retention: 95 },
  { month: '2026-02', retention: 88 },
  { month: '2026-03', retention: 82 },
]

const revenuePayload = [
  { month: '2026-02', revenue: 600 },
  { month: '2026-03', revenue: 800 },
]

const activePayload = {
  daily: 11,
  weekly: 29,
  trend_daily: '+2',
  trend_weekly: '+5',
}

const loginPayload = {
  items: [
    {
      id: 100,
      username: 'zhangsan',
      action: '登录',
      ip: '127.0.0.1',
      time: '2026-04-15 12:00:00',
      status: '成功',
    },
  ],
  total: 25,
  page: 1,
  page_size: 20,
}

const adminPayload = {
  items: [
    {
      id: 201,
      admin: 'admin',
      action: 'create_user',
      time: '2026-04-15 13:00:00',
    },
  ],
  total: 21,
  page: 1,
  page_size: 20,
}

const ordersPayload = {
  items: [
    {
      order_id: 'ORD_001',
      username: 'robert',
      amount: 99.0,
      order_type: 'professional',
      status: 'SUCCESS',
      created_at: '1778000000',
    },
  ],
  total: 5,
  page: 1,
  page_size: 20,
}

function setupApiMocks() {
  statisticsAPI.getOverview.mockResolvedValue(overviewPayload)
  statisticsAPI.getRetention.mockResolvedValue(retentionPayload)
  statisticsAPI.getRevenue.mockResolvedValue(revenuePayload)
  statisticsAPI.getLoginLogs.mockResolvedValue(loginPayload)
  statisticsAPI.getAdminLogs.mockResolvedValue(adminPayload)
  statisticsAPI.getActiveUsers.mockResolvedValue(activePayload)
  statisticsAPI.getOrders.mockResolvedValue(ordersPayload)
}

describe('StatisticsPage', async () => {
  const { default: StatisticsPage } = await import('../pages/StatisticsPage')

  beforeEach(() => {
    vi.clearAllMocks()
    setupApiMocks()
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:mock-url'),
      revokeObjectURL: vi.fn(),
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('renders heading and loads overview data from APIs', async () => {
    render(<StatisticsPage />)

    expect(screen.getByText(/数据统计/)).toBeInTheDocument()

    await waitFor(() => {
      expect(statisticsAPI.getOverview).toHaveBeenCalled()
      expect(screen.getAllByText('42').length).toBeGreaterThan(0)
      expect(screen.getByText('95%')).toBeInTheDocument()
    })
  })

  it('renders all seven tabs', () => {
    render(<StatisticsPage />)

    expect(screen.getByRole('tab', { name: '总览' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '留存分析' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '用户活跃' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '充值与收入' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '操作日志' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '登录记录' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '订单记录' })).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: '异常监控' })).not.toBeInTheDocument()
  })

  it('renders overview metrics from API payload', async () => {
    render(<StatisticsPage />)

    await waitFor(() => {
      expect(screen.getByText('总用户数')).toBeInTheDocument()
      expect(screen.getByText('活跃用户')).toBeInTheDocument()
      expect(screen.getByText('今日新增')).toBeInTheDocument()
      expect(screen.getByText('总收入')).toBeInTheDocument()
      expect(screen.getAllByText('42').length).toBeGreaterThan(0)
      expect(screen.getAllByText('18').length).toBeGreaterThan(0)
      expect(screen.getAllByText('3').length).toBeGreaterThan(0)
      expect(screen.getByText('1234.56')).toBeInTheDocument()
      expect(screen.getByText('专业版用户')).toBeInTheDocument()
      expect(screen.getByText('效率版用户')).toBeInTheDocument()
      expect(screen.getByText('免费版用户')).toBeInTheDocument()
      expect(screen.getByText('95%')).toBeInTheDocument()
      expect(screen.getByText('88%')).toBeInTheDocument()
      expect(screen.getByText('82%')).toBeInTheDocument()
    })
  })

  it('renders login logs table columns and rows', async () => {
    render(<StatisticsPage />)

    fireEvent.click(screen.getByRole('tab', { name: '登录记录' }))

    await waitFor(() => {
      expect(screen.getByRole('columnheader', { name: 'ID' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: '用户名' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: '操作' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: 'IP地址' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: '时间' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: '状态' })).toBeInTheDocument()
      expect(screen.getByText('zhangsan')).toBeInTheDocument()
      expect(screen.getByText('127.0.0.1')).toBeInTheDocument()
      expect(screen.getByText('成功')).toBeInTheDocument()
    })
  })

  it('renders admin logs table columns and rows', async () => {
    render(<StatisticsPage />)

    fireEvent.click(screen.getByRole('tab', { name: '操作日志' }))

    await waitFor(() => {
      expect(screen.getByRole('columnheader', { name: 'ID' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: '管理员' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: '操作内容' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: '时间' })).toBeInTheDocument()
      expect(screen.getByText('admin')).toBeInTheDocument()
      expect(screen.getByText('create_user')).toBeInTheDocument()
    })
  })

  it('passes search text to login logs API after debounce', async () => {
    render(<StatisticsPage />)

    await waitFor(() => {
      expect(statisticsAPI.getLoginLogs).toHaveBeenCalledWith(1, 20, '', '', '')
    })

    fireEvent.click(screen.getByRole('tab', { name: '登录记录' }))
    fireEvent.change(screen.getByPlaceholderText('搜索用户'), {
      target: { value: 'zhang' },
    })

    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 400))
    })

    await waitFor(() => {
      expect(statisticsAPI.getLoginLogs).toHaveBeenLastCalledWith(1, 20, 'zhang', '', '')
    })
  })

  it('supports admin logs pagination', async () => {
    render(<StatisticsPage />)

    await waitFor(() => {
      expect(statisticsAPI.getAdminLogs).toHaveBeenCalledWith(1, 20, '', '', '')
    })

    fireEvent.click(screen.getByRole('tab', { name: '操作日志' }))
    expect(screen.getByText('共 21 条')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '下一页' }))

    await waitFor(() => {
      expect(statisticsAPI.getAdminLogs).toHaveBeenLastCalledWith(2, 20, '', '', '')
    })
  })

  it('shows API totals instead of current items length', async () => {
    render(<StatisticsPage />)

    fireEvent.click(screen.getByRole('tab', { name: '登录记录' }))
    await waitFor(() => {
      expect(screen.getByText('共 25 条')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('tab', { name: '操作日志' }))
    await waitFor(() => {
      expect(screen.getByText('共 21 条')).toBeInTheDocument()
    })
  })

  it('exports login logs to CSV', async () => {
    const appendSpy = vi.spyOn(document.body, 'appendChild')
    const removeSpy = vi.spyOn(document.body, 'removeChild')
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    render(<StatisticsPage />)
    fireEvent.click(screen.getByRole('tab', { name: '登录记录' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '导出登录记录' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: '导出登录记录' }))

    expect(URL.createObjectURL).toHaveBeenCalled()
    expect(clickSpy).toHaveBeenCalled()
    expect(appendSpy).toHaveBeenCalled()
    expect(removeSpy).toHaveBeenCalled()

    clickSpy.mockRestore()
    appendSpy.mockRestore()
    removeSpy.mockRestore()
  })

  it('renders orders tab with table columns and data', async () => {
    render(<StatisticsPage />)

    fireEvent.click(screen.getByRole('tab', { name: '订单记录' }))

    await waitFor(() => {
      expect(screen.getByRole('columnheader', { name: '订单号' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: '用户名' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: '金额' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: '套餐类型' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: '状态' })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: '创建时间' })).toBeInTheDocument()
      expect(screen.getByText('ORD_001')).toBeInTheDocument()
      expect(screen.getByText('robert')).toBeInTheDocument()
      expect(screen.getByText('共 5 条')).toBeInTheDocument()
    })
  })

  it('passes search text to orders API after debounce', async () => {
    render(<StatisticsPage />)

    await waitFor(() => {
      expect(statisticsAPI.getOrders).toHaveBeenCalledWith(1, 20, '', '', '', '')
    })

    fireEvent.click(screen.getByRole('tab', { name: '订单记录' }))
    fireEvent.change(screen.getByPlaceholderText('搜索用户/订单号'), {
      target: { value: 'robert' },
    })

    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 400))
    })

    await waitFor(() => {
      expect(statisticsAPI.getOrders).toHaveBeenLastCalledWith(1, 20, 'robert', '', '', '')
    })
  })

  it('passes status filter to orders API', async () => {
    render(<StatisticsPage />)

    fireEvent.click(screen.getByRole('tab', { name: '订单记录' }))

    await waitFor(() => {
      expect(statisticsAPI.getOrders).toHaveBeenCalled()
    })

    const select = screen.getByTestId('mock-select')
    fireEvent.change(select, { target: { value: 'SUCCESS' } })

    await waitFor(() => {
      expect(statisticsAPI.getOrders).toHaveBeenLastCalledWith(1, 20, '', 'SUCCESS', '', '')
    })
  })
})
