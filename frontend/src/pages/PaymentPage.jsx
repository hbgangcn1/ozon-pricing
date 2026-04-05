import { useState } from 'react'
import { Download, Search, Maximize2, RefreshCw, Info } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Badge } from '../components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table'
import { toast } from 'sonner'

const mockOrders = [
  { id: 'ORD20260322001', plan: '专业版', amount: 149, status: '已支付', createTime: '2026-03-22 10:30:15', payTime: '2026-03-22 10:31:02' },
  { id: 'ORD20260321001', plan: '效率版', amount: 9.9, status: '已支付', createTime: '2026-03-21 14:22:30', payTime: '2026-03-21 14:23:15' },
  { id: 'ORD20260315001', plan: '专业版', amount: 149, status: '已支付', createTime: '2026-03-15 09:15:45', payTime: '2026-03-15 09:16:30' },
  { id: 'ORD20260310001', plan: '效率版', amount: 99, status: '已支付', createTime: '2026-03-10 16:40:20', payTime: '2026-03-10 16:41:05' },
  { id: 'ORD20260305001', plan: '专业版', amount: 1499, status: '已支付', createTime: '2026-03-05 11:20:10', payTime: '2026-03-05 11:21:00' },
  { id: 'ORD20260301001', plan: '免费版', amount: 0, status: '已支付', createTime: '2026-03-01 08:00:00', payTime: '2026-03-01 08:00:00' },
  { id: 'ORD20260228001', plan: '效率版', amount: 9.9, status: '已支付', createTime: '2026-02-28 20:15:30', payTime: '2026-02-28 20:16:12' },
  { id: 'ORD20260225001', plan: '专业版', amount: 149, status: '已支付', createTime: '2026-02-25 13:45:00', payTime: '2026-02-25 13:46:00' },
  { id: 'ORD20260220001', plan: '企业版', amount: 999, status: '已支付', createTime: '2026-02-20 15:30:45', payTime: '2026-02-20 15:32:00' },
  { id: 'ORD20260215001', plan: '效率版', amount: 99, status: '已支付', createTime: '2026-02-15 10:20:30', payTime: '2026-02-15 10:21:15' },
]

function PaymentPage() {
  const [searchText, setSearchText] = useState('')
  const [fullscreen, setFullscreen] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 10

  const filteredData = mockOrders.filter(o => 
    o.id.toLowerCase().includes(searchText.toLowerCase()) ||
    o.plan.toLowerCase().includes(searchText.toLowerCase())
  )

  const total = filteredData.length
  const totalPages = Math.ceil(total / pageSize)
  const paginatedData = filteredData.slice((currentPage - 1) * pageSize, currentPage * pageSize)

  const handleExportCSV = () => {
    const headers = ['订单号,套餐,金额,状态,创建时间,支付时间']
    const rows = filteredData.map(o => `${o.id},${o.plan},${o.amount},${o.status},${o.createTime},${o.payTime}`)
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
    <div className={`space-y-6 ${fullscreen ? 'fixed inset-0 z-50 bg-surface p-6 overflow-auto' : ''}`}>
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
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle>📋 订单历史</CardTitle>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-text-muted" />
              <Input
                placeholder="搜索订单号或套餐"
                value={searchText}
                onChange={e => {
                  setSearchText(e.target.value)
                  setCurrentPage(1)
                }}
                className="pl-10 w-64 transition-all duration-200"
              />
            </div>
            <Button variant="outline" size="icon" onClick={() => toast.info('刷新中...')} className="transition-all duration-200">
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button variant="outline" onClick={handleExportCSV} className="transition-all duration-200">
              <Download className="h-4 w-4 mr-2" />
              导出CSV
            </Button>
            <Button variant="outline" size="icon" onClick={() => setFullscreen(!fullscreen)} className="transition-all duration-200">
              <Maximize2 className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[180px]">订单号</TableHead>
                <TableHead className="w-[100px]">套餐</TableHead>
                <TableHead className="w-[100px]">金额（元）</TableHead>
                <TableHead className="w-[100px]">状态</TableHead>
                <TableHead className="w-[160px]">创建时间</TableHead>
                <TableHead className="w-[160px]">支付时间</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {paginatedData.map((order) => (
                <TableRow key={order.id}>
                  <TableCell className="font-mono text-sm">{order.id}</TableCell>
                  <TableCell>{order.plan}</TableCell>
                  <TableCell>¥{order.amount.toFixed(2)}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="border-green-500/30 text-green-400">
                      {order.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-text-secondary">{order.createTime}</TableCell>
                  <TableCell className="text-text-secondary">{order.payTime}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          
          {/* 分页 */}
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
        </CardContent>
      </Card>
    </div>
  )
}

export default PaymentPage
