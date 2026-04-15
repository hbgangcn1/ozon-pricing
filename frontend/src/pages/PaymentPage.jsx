import { useState, useEffect, useCallback } from 'react'
import { Download, Search, Maximize2, Minimize2, RefreshCw, Info } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Badge } from '../components/ui/badge'
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from '../components/ui/select'
import { Skeleton } from '../components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table'
import { toast } from 'sonner'
import { useNavigate } from 'react-router-dom'
import { ordersAPI } from '../services/api'

function getStatusBadge(status) {
  const map = {
    SUCCESS: { label: '已支付', className: 'border-status-success/30 text-status-success' },
    PENDING: { label: '待支付', className: 'border-status-warning/30 text-status-warning' },
    FAILED: { label: '支付失败', className: 'border-status-error/30 text-status-error' },
    CLOSED: { label: '已关闭', className: 'border-status-error/30 text-status-error' },
  }
  const info = map[status] || { label: status, className: 'border-surface-high text-text-secondary' }
  return <Badge variant="outline" className={info.className}>{info.label}</Badge>
}

function getPlanName(orderType) {
  const map = { free: '免费版', efficiency: '效率版', professional: '专业版', enterprise: '企业版' }
  return map[orderType] || orderType || '-'
}

function PaymentPage() {
  const navigate = useNavigate()
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState('all')
  const [searchText, setSearchText] = useState('')
  const [fullscreen, setFullscreen] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [total, setTotal] = useState(0)
  const pageSize = 10

  const fetchOrders = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page: currentPage, page_size: pageSize }
      if (statusFilter !== 'all') params.status = statusFilter
      const data = await ordersAPI.getAll(params)
      setOrders(data.orders || [])
      setTotal(data.total || 0)
    } catch (err) {
      toast.error('获取订单失败')
    } finally {
      setLoading(false)
    }
  }, [currentPage, statusFilter])

  useEffect(() => {
    fetchOrders()
  }, [fetchOrders])

  const filteredOrders = orders.filter(o => 
    (o.order_id || '').toLowerCase().includes(searchText.toLowerCase()) ||
    (o.description || '').toLowerCase().includes(searchText.toLowerCase()) ||
    getPlanName(o.order_type).toLowerCase().includes(searchText.toLowerCase())
  )

  const totalPages = Math.ceil(total / pageSize)

  const handleExportCSV = () => {
    const headers = ['订单号,套餐,金额,状态,创建时间']
    const statusMap = { SUCCESS: '已支付', PENDING: '待支付', FAILED: '支付失败', CLOSED: '已关闭' }
    const rows = filteredOrders.map(o => 
      `${o.order_id},${getPlanName(o.order_type)},¥${(o.amount / 100).toFixed(2)},${statusMap[o.status] || o.status},${new Date(o.created_at * 1000).toLocaleString('zh-CN')}`
    )
    const csv = [headers, ...rows].join('\n')
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `订单记录_${new Date().toISOString().slice(0,10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('导出成功')
  }

  return (
    <div className={`space-y-6 w-full max-w-full overflow-x-hidden ${fullscreen ? 'fixed inset-0 z-50 bg-surface p-6 overflow-auto' : ''}`}>
      <h1 className="text-xl font-semibold font-headline tracking-tight text-text-primary">
        💳 支付与订单管理
      </h1>
      
      <div className="bg-primary/10 border border-primary/20 rounded-lg p-4 flex items-start gap-3">
        <Info className="w-5 h-5 text-primary-dim mt-0.5" />
        <p className="text-sm text-text-secondary">
          💡 如需订阅或升级套餐，请前往「订阅管理」页面
        </p>
      </div>

      <Card>
        <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center justify-between space-y-4 sm:space-y-0 pb-2">
          <CardTitle>📋 订单历史</CardTitle>
          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
            <div className="relative flex-1 min-w-[200px] sm:min-w-0 sm:w-auto">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-text-muted" />
              <Input
                placeholder="搜索订单号或套餐"
                value={searchText}
                onChange={e => setSearchText(e.target.value)}
                className="pl-10 w-full sm:w-64 transition-all duration-200"
              />
            </div>
            
            <Select value={statusFilter} onValueChange={(val) => { setStatusFilter(val); setCurrentPage(1) }}>
              <SelectTrigger className="w-[120px]">
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部状态</SelectItem>
                <SelectItem value="SUCCESS">已支付</SelectItem>
                <SelectItem value="PENDING">待支付</SelectItem>
                <SelectItem value="CLOSED">已关闭</SelectItem>
              </SelectContent>
            </Select>

            <div className="flex items-center gap-2">
              <Button aria-label="刷新" variant="outline" size="icon" onClick={() => { fetchOrders(); toast.success('刷新成功') }} className="transition-all duration-200">
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
              <Button variant="outline" onClick={handleExportCSV} className="transition-all duration-200">
                <Download className="h-4 w-4 mr-2" />
                <span className="hidden sm:inline">导出CSV</span>
                <span className="sm:hidden">导出</span>
              </Button>
              <Button aria-label="全屏" variant="outline" size="icon" onClick={() => setFullscreen(!fullscreen)} className="transition-all duration-200">
                {fullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto w-full">
            <Table className="min-w-max">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-32 sm:w-[180px]">订单号</TableHead>
                  <TableHead className="w-20 sm:w-[100px]">套餐</TableHead>
                  <TableHead className="w-20 sm:w-[100px]">金额（元）</TableHead>
                  <TableHead className="w-20 sm:w-[100px]">状态</TableHead>
                  <TableHead className="w-24 sm:w-[160px]">创建时间</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={`skeleton-${i}`}>
                      <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                    </TableRow>
                  ))
                ) : filteredOrders.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="h-48">
                      <div className="flex flex-col items-center justify-center space-y-4 text-center">
                        <p className="text-text-secondary">暂无订单记录</p>
                        <p className="text-sm text-text-muted">升级套餐后将在此显示订单信息</p>
                        <Button variant="outline" onClick={() => navigate('/subscription')}>
                          前往订阅管理
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredOrders.map((order) => (
                    <TableRow key={order.order_id}>
                      <TableCell className="font-mono text-sm">{order.order_id}</TableCell>
                      <TableCell>{getPlanName(order.order_type)}</TableCell>
                      <TableCell>¥{(order.amount / 100).toFixed(2)}</TableCell>
                      <TableCell>{getStatusBadge(order.status)}</TableCell>
                      <TableCell className="text-text-secondary">
                        {new Date(order.created_at * 1000).toLocaleString('zh-CN')}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
          
          {/* 分页 */}
          {!loading && total > 0 && (
            <div className="flex items-center justify-between mt-4">
              <div className="text-sm text-text-secondary">
                共 {total} 条记录，第 {currentPage} / {totalPages} 页
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="transition-all duration-200"
                >
                  上一页
                </Button>
                <div className="flex items-center gap-1">
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    let pageNum
                    if (totalPages <= 5) {
                      pageNum = i + 1
                    } else if (currentPage <= 3) {
                      pageNum = i + 1
                    } else if (currentPage >= totalPages - 2) {
                      pageNum = totalPages - 4 + i
                    } else {
                      pageNum = currentPage - 2 + i
                    }
                    return (
                      <Button
                        key={pageNum}
                        variant={currentPage === pageNum ? "default" : "outline"}
                        size="sm"
                        className={`w-8 h-8 transition-all duration-200 ${currentPage === pageNum ? 'bg-primary text-white hover:bg-primary-dim' : ''}`}
                        onClick={() => setCurrentPage(pageNum)}
                      >
                        {pageNum}
                      </Button>
                    )
                  })}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="transition-all duration-200"
                >
                  下一页
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default PaymentPage