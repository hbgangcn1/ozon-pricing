import { useState, useEffect , useMemo } from 'react'
import { UserPlus, Key, Trash2, RefreshCw, Search, X, User, Lock, Shield } from 'lucide-react'
import { toast } from 'sonner'
import { adminAPI } from '../services/api'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Badge } from '../components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card'

function UserManagementPage() {
  const [selectedUser, setSelectedUser] = useState(null)
  const [addUserVisible, setAddUserVisible] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [syncDialogOpen, setSyncDialogOpen] = useState(false)
  const [subscriptionDialogOpen, setSubscriptionDialogOpen] = useState(false)
  const [subscriptionTarget, setSubscriptionTarget] = useState(null)
  const [subscriptionDays, setSubscriptionDays] = useState('')
  const [calculationDelta, setCalculationDelta] = useState('')
  const [selectedUserType, setSelectedUserType] = useState('')
  const [loadingDays, setLoadingDays] = useState(false)
  const [loadingDelta, setLoadingDelta] = useState(false)
  const [loadingType, setLoadingType] = useState(false)

  const [formData, setFormData] = useState({
    username: '',
    password: '',
    role: 'user'
  })
  const [_selectedUsersForSync, setSelectedUsersForSync] = useState([])
  const [users, setUsers] = useState([])
  const [_loading, setLoading] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  const [pageSize] = useState(20)

  // 获取用户列表
  const fetchUsers = async (page = 1, pageSize = 20, keyword = '') => {
    setLoading(true)
    try {
      const response = await adminAPI.getUsers(page, pageSize, keyword)
      const data = response
      setUsers(data.users || [])
      setTotal(data.total || 0)
      setCurrentPage(data.page || page)
      setTotalPages(Math.ceil((data.total || 0) / pageSize))
    } catch (error) {
      toast.error(error.userMessage || error.response?.data?.detail || '获取用户列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    const loadUsers = async () => {
      setLoading(true)
      try {
        const response = await adminAPI.getUsers(1, 20, '')
        if (!controller.signal.aborted) {
          setUsers(response.users || [])
          setTotal(response.total || 0)
          setCurrentPage(response.page || 1)
          setTotalPages(Math.ceil((response.total || 0) / 20))
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          toast.error(error.userMessage || error.response?.data?.detail || '获取用户列表失败')
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }
    loadUsers()
    return () => controller.abort()
  }, [])

  const filteredUsers = useMemo(() => users.filter(u =>
    u.username.toLowerCase().includes(searchText.toLowerCase())
  ), [users, searchText])

  const handleAddUser = async (e) => {
    e.preventDefault()
    if (!formData.username || !formData.password) {
      toast.error('请填写所有必填字段')
      return
    }
    try {
      await adminAPI.createUser({
        username: formData.username,
        password: formData.password,
        role: formData.role,
      })
      toast.success('用户创建成功')
      setAddUserVisible(false)
      setFormData({ username: '', password: '', role: 'user', user_type: 'free' })
      fetchUsers() // 刷新列表
    } catch (error) {
      toast.error(error.userMessage || error.response?.data?.detail || '创建用户失败')
    }
  }

  const handleResetPassword = async (user) => {
    try {
      await adminAPI.resetPassword(user.id)
      toast.success(`密码已重置为默认密码: ${user.username}123`)
    } catch (error) {
      toast.error(error.response?.data?.detail || '重置密码失败')
    }
  }

  const handleDeleteUser = async (user) => {
    try {
      await adminAPI.deleteUser(user.id)
      toast.success(`用户 ${user.username} 已删除`)
      setSelectedUser(null)
      fetchUsers(currentPage, pageSize, searchText)
    } catch (error) {
      toast.error(error.response?.data?.detail || '删除用户失败')
    }
  }

  const handleSyncLogistics = () => {
    toast.success('物流规则同步完成')
    setSyncDialogOpen(false)
    setSelectedUsersForSync([])
  }

  const handleFormChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const handleExtendSubscription = async () => {
    if (!subscriptionDays || isNaN(subscriptionDays)) {
      toast.error('请输入有效的天数')
      return
    }
    setLoadingDays(true)
    try {
      await adminAPI.extendSubscription(subscriptionTarget.id, parseInt(subscriptionDays, 10))
      toast.success('到期时间调整成功')
      setSubscriptionDays('')
      fetchUsers(currentPage, pageSize, searchText)
    } catch (error) {
      toast.error(error.userMessage || error.response?.data?.detail || '到期时间调整失败')
    } finally {
      setLoadingDays(false)
    }
  }

  const handleAdjustCalculations = async () => {
    if (!calculationDelta || isNaN(calculationDelta)) {
      toast.error('请输入有效的次数')
      return
    }
    setLoadingDelta(true)
    try {
      await adminAPI.adjustCalculations(subscriptionTarget.id, parseInt(calculationDelta, 10))
      toast.success('次数调整成功')
      setCalculationDelta('')
      fetchUsers(currentPage, pageSize, searchText)
    } catch (error) {
      toast.error(error.userMessage || error.response?.data?.detail || '次数调整失败')
    } finally {
      setLoadingDelta(false)
    }
  }

  const handleSetUserType = async () => {
    if (!selectedUserType) {
      toast.error('请选择用户类型')
      return
    }
    setLoadingType(true)
    try {
      await adminAPI.setUserType(subscriptionTarget.id, selectedUserType)
      toast.success('用户类型调整成功')
      fetchUsers(currentPage, pageSize, searchText)
    } catch (error) {
      toast.error(error.userMessage || error.response?.data?.detail || '用户类型调整失败')
    } finally {
      setLoadingType(false)
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-text-primary font-headline tracking-tight">
        👥 用户管理 — 管理系统用户
      </h1>

      {/* 添加新用户表单 */}
      <Card>
        <CardHeader>
          <CardTitle>➕ 添加新用户</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAddUser} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label htmlFor="username">用户名</Label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
                  <Input
                    id="username"
                    placeholder="请输入用户名"
                    value={formData.username}
                    onChange={(e) => handleFormChange('username', e.target.value)}
                    className="pl-10"
                    required
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="password">初始密码</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
                  <Input
                    id="password"
                    type="password"
                    placeholder="请输入密码"
                    value={formData.password}
                    onChange={(e) => handleFormChange('password', e.target.value)}
                    className="pl-10"
                    required
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="role">角色</Label>
                <div className="relative">
                  <Shield className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted z-10" />
                  <Select value={formData.role} onValueChange={(value) => handleFormChange('role', value)}>
                    <SelectTrigger className="pl-10 transition-all duration-200">
                      <SelectValue placeholder="选择角色" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="admin">admin</SelectItem>
                      <SelectItem value="user">user</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label>用户类型</Label>
                <Select value={formData.user_type} onValueChange={(value) => handleFormChange('user_type', value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择类型" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="free">免费版</SelectItem>
                    <SelectItem value="efficiency">效率版</SelectItem>
                    <SelectItem value="professional">专业版</SelectItem>
                    <SelectItem value="enterprise">企业版</SelectItem>
                    <SelectItem value="testing">测试版</SelectItem>
                    <SelectItem value="gratitude">感谢版</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-end">
                <Button type="submit" className="w-full transition-all duration-200">
                  <UserPlus className="w-4 h-4 mr-2" />
                  创建用户
                </Button>
              </div>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* 批量物流规则同步 */}
      <Card>
        <CardHeader>
          <CardTitle>📦 批量物流规则同步</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col md:flex-row items-start md:items-center gap-4">
            <p className="text-text-secondary">将物流规则同步给指定用户</p>
            <div className="flex-1 w-full md:w-auto">
              <Select>
                <SelectTrigger>
                  <SelectValue placeholder="选择用户" />
                </SelectTrigger>
                <SelectContent>
                  {users.filter(u => u.role !== 'admin').map(u => (
                    <SelectItem key={u.id} value={u.id.toString()}>
                      {u.username}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button variant="outline" onClick={() => setSyncDialogOpen(true)}>
              <RefreshCw className="w-4 h-4 mr-2" />
              同步物流规则
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 用户列表 */}
      <Card>
        <CardHeader>
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <CardTitle>👥 用户列表</CardTitle>
            <div className="relative w-full md:w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
              <Input
                placeholder="搜索用户名"
                value={searchText}
                onChange={e => setSearchText(e.target.value)}
                className="pl-10"
              />
              {searchText && (
                <button
                  onClick={() => setSearchText('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
                  aria-label="关闭"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2 mb-4">
            <Button onClick={() => setAddUserVisible(true)}>
              <UserPlus className="w-4 h-4 mr-2" />
              添加新用户
            </Button>
            <Button variant="outline" onClick={() => toast.info('刷新中...')}>
              <RefreshCw className="w-4 h-4 mr-2" />
              刷新
            </Button>
          </div>
          
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-16">ID</TableHead>
                <TableHead>用户名</TableHead>
                <TableHead className="w-24">角色</TableHead>
                <TableHead className="w-24">订阅</TableHead>
                <TableHead className="w-24">状态</TableHead>
                <TableHead className="w-24">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredUsers.map(user => (
                <TableRow 
                  key={user.id}
                  onClick={() => setSelectedUser(user)}
                  className={`cursor-pointer ${selectedUser?.id === user.id ? 'bg-surface-container/50' : ''}`}
                >
                  <TableCell className="font-medium">{user.id}</TableCell>
                  <TableCell className="font-semibold">{user.username}</TableCell>
                  <TableCell>
                    <Badge variant={user.role === 'admin' ? 'default' : 'secondary'}>
                      {user.role}
                    </Badge>
                  </TableCell>
                  <TableCell>{user.user_type}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="border-status-success/30 text-status-success">
                      {user.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Button 
                      variant="outline" 
                      size="sm" 
                      onClick={(e) => {
                        e.stopPropagation()
                        setSubscriptionTarget(user)
                        setSelectedUserType(user.user_type || 'free')
                        setSubscriptionDialogOpen(true)
                      }}
                    >
                      订阅
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-surface-high">
            <p className="text-sm text-text-secondary">共 {total} 条，第 {currentPage}/{totalPages} 页</p>
            <div className="flex gap-2">
              <Button 
                variant="outline" 
                size="sm" 
                disabled={currentPage <= 1}
                onClick={() => fetchUsers(currentPage - 1, pageSize, searchText)}
              >
                上一页
              </Button>
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let pageNum;
                if (totalPages <= 5) {
                  pageNum = i + 1;
                } else if (currentPage <= 3) {
                  pageNum = i + 1;
                } else if (currentPage >= totalPages - 2) {
                  pageNum = totalPages - 4 + i;
                } else {
                  pageNum = currentPage - 2 + i;
                }
                return (
                  <Button
                    key={pageNum}
                    variant="outline"
                    size="sm"
                    className={currentPage === pageNum ? 'bg-surface-high' : ''}
                    onClick={() => fetchUsers(pageNum, pageSize, searchText)}
                  >
                    {pageNum}
                  </Button>
                );
              })}
              <Button 
                variant="outline" 
                size="sm" 
                disabled={currentPage >= totalPages}
                onClick={() => fetchUsers(currentPage + 1, pageSize, searchText)}
              >
                下一页
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 用户操作 */}
      {selectedUser && (
        <Card>
          <CardHeader>
            <CardTitle>🛠️ 用户操作</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div>
                <p className="text-sm text-text-secondary">用户ID</p>
                <p className="text-text-primary">{selectedUser.id}</p>
              </div>
              <div>
                <p className="text-sm text-text-secondary">用户名</p>
                <p className="text-text-primary">{selectedUser.username}</p>
              </div>
              <div>
                <p className="text-sm text-text-secondary">角色</p>
                <p className="text-text-primary">{selectedUser.role}</p>
              </div>
              <div>
                <p className="text-sm text-text-secondary">订阅</p>
                <p className="text-text-primary">{selectedUser.user_type}</p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => handleResetPassword(selectedUser)}>
                <Key className="w-4 h-4 mr-2" />
                🔒 重置密码
              </Button>
              <Button 
                variant="destructive" 
                onClick={() => {
                  if (window.confirm(`确认删除用户 ${selectedUser.username}？`)) {
                    handleDeleteUser(selectedUser)
                  }
                }}
              >
                <Trash2 className="w-4 h-4 mr-2" />
                🗑️ 删除用户
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 添加用户对话框 */}
      <Dialog open={addUserVisible} onOpenChange={setAddUserVisible}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>添加新用户</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleAddUser} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="modal-username">用户名</Label>
              <Input
                id="modal-username"
                placeholder="请输入用户名"
                value={formData.username}
                onChange={(e) => handleFormChange('username', e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="modal-password">初始密码</Label>
              <Input
                id="modal-password"
                type="password"
                placeholder="请输入密码"
                value={formData.password}
                onChange={(e) => handleFormChange('password', e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="modal-role">角色</Label>
              <Select value={formData.role} onValueChange={(value) => handleFormChange('role', value)}>
                <SelectTrigger>
                  <SelectValue placeholder="选择角色" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">admin</SelectItem>
                  <SelectItem value="user">user</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="modal-user-type">用户类型</Label>
              <Select value={formData.user_type} onValueChange={(value) => handleFormChange('user_type', value)}>
                <SelectTrigger>
                  <SelectValue placeholder="选择类型" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="free">免费版</SelectItem>
                  <SelectItem value="efficiency">效率版</SelectItem>
                  <SelectItem value="professional">专业版</SelectItem>
                  <SelectItem value="enterprise">企业版</SelectItem>
                  <SelectItem value="testing">测试版</SelectItem>
                  <SelectItem value="gratitude">感谢版</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setAddUserVisible(false)}>
                取消
              </Button>
              <Button type="submit">
                创建用户
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* 同步对话框 */}
      <Dialog open={syncDialogOpen} onOpenChange={setSyncDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>批量同步物流规则</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-text-secondary">选择要同步物流规则的用户</p>
            <Select>
              <SelectTrigger>
                <SelectValue placeholder="选择用户" />
              </SelectTrigger>
              <SelectContent>
                {users.filter(u => u.role !== 'admin').map(u => (
                  <SelectItem key={u.id} value={u.id.toString()}>
                    {u.username}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSyncDialogOpen(false)}>
              取消
            </Button>
            <Button onClick={handleSyncLogistics}>
              <RefreshCw className="w-4 h-4 mr-2" />
              同步
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 订阅管理对话框 */}
      <Dialog open={subscriptionDialogOpen} onOpenChange={setSubscriptionDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>订阅管理 - {subscriptionTarget?.username}</DialogTitle>
          </DialogHeader>
          <div className="space-y-6 py-4">
            
            <div className="space-y-3">
              <Label>到期时间调整（天）</Label>
              <div className="flex gap-2">
                <Input 
                  type="number" 
                  placeholder="正数延长，负数缩短" 
                  value={subscriptionDays}
                  onChange={(e) => setSubscriptionDays(e.target.value)}
                />
                <Button onClick={handleExtendSubscription} disabled={loadingDays}>
                  {loadingDays ? '提交中...' : '调整'}
                </Button>
              </div>
            </div>

            <div className="space-y-3">
              <Label>当日次数调整</Label>
              <div className="flex gap-2">
                <Input 
                  type="number" 
                  placeholder="正数增加，负数减少" 
                  value={calculationDelta}
                  onChange={(e) => setCalculationDelta(e.target.value)}
                />
                <Button onClick={handleAdjustCalculations} disabled={loadingDelta}>
                  {loadingDelta ? '提交中...' : '调整'}
                </Button>
              </div>
            </div>

            <div className="space-y-3">
              <Label>用户类型修改</Label>
              <div className="flex gap-2">
                <Select value={selectedUserType} onValueChange={setSelectedUserType}>
                  <SelectTrigger className="flex-1">
                    <SelectValue placeholder="选择类型" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="free">免费版</SelectItem>
                    <SelectItem value="efficiency">效率版</SelectItem>
                    <SelectItem value="professional">专业版</SelectItem>
                    <SelectItem value="enterprise">企业版</SelectItem>
                    <SelectItem value="test">测试版</SelectItem>
                    <SelectItem value="thanks">感谢版</SelectItem>
                  </SelectContent>
                </Select>
                <Button onClick={handleSetUserType} disabled={loadingType}>
                  {loadingType ? '提交中...' : '修改'}
                </Button>
              </div>
            </div>
            
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default UserManagementPage
