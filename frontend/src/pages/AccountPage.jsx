import { useState } from 'react'
import { Key, ShieldCheck } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card'
import { toast } from 'sonner'
import { authAPI } from '../services/api'
import { useAuthStore } from '../stores/authStore'

function AccountPage() {
  const [loading, setLoading] = useState(false)
  const { user } = useAuthStore()
  const [formData, setFormData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  })

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    if (formData.new_password !== formData.confirm_password) {
      toast.error('新密码与确认密码不匹配')
      return
    }

    setLoading(true)
    try {
      await authAPI.changePassword({
        current_password: formData.current_password,
        new_password: formData.new_password,
      })
      toast.success('密码修改成功')
      setFormData({
        current_password: '',
        new_password: '',
        confirm_password: '',
      })
    } catch (error) {
      toast.error(error.response?.data?.detail || '密码修改失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold font-headline tracking-tight text-text-primary">
        🔐 账户管理 — 管理账户信息和密码
      </h1>

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>🔒 修改密码</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-text-secondary">当前密码</label>
              <div className="relative">
                <Key className="absolute left-3 top-3 h-4 w-4 text-text-muted" />
                <input
                  type="password"
                  name="current_password"
                  placeholder="请输入当前密码"
                  value={formData.current_password}
                  onChange={handleChange}
                  required
                  className="w-full rounded-md border border-surface-highest bg-surface py-2 pl-10 pr-3 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all duration-200"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-text-secondary">新密码</label>
              <div className="relative">
                <ShieldCheck className="absolute left-3 top-3 h-4 w-4 text-text-muted" />
                <input
                  type="password"
                  name="new_password"
                  placeholder="请输入新密码（至少13位）"
                  value={formData.new_password}
                  onChange={handleChange}
                  required
                  minLength={13}
                  className="w-full rounded-md border border-surface-highest bg-surface py-2 pl-10 pr-3 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all duration-200"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-text-secondary">确认新密码</label>
              <div className="relative">
                <ShieldCheck className="absolute left-3 top-3 h-4 w-4 text-text-muted" />
                <input
                  type="password"
                  name="confirm_password"
                  placeholder="请再次输入新密码"
                  value={formData.confirm_password}
                  onChange={handleChange}
                  required
                  className="w-full rounded-md border border-surface-highest bg-surface py-2 pl-10 pr-3 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all duration-200"
                />
              </div>
            </div>

            <div className="border-t border-surface-high pt-4">
              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-md bg-primary py-2 px-4 text-sm font-medium text-white hover:bg-primary-dim focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-surface-container transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? '修改中...' : '修改密码'}
              </button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>ℹ️ 账户信息</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex">
            <span className="text-text-secondary w-24">用户名：</span>
            <span className="text-text-primary">{user?.username || '-'}</span>
          </div>
          <div className="flex">
            <span className="text-text-secondary w-24">用户角色：</span>
            <span className={`text-text-primary ${user?.role === 'admin' ? 'text-red-400' : ''}`}>
              {user?.role === 'admin' ? '管理员' : '普通用户'}
            </span>
          </div>
          <div className="flex">
            <span className="text-text-secondary w-24">订阅类型：</span>
            <span className="text-text-primary">{user?.user_type || 'free'}</span>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default AccountPage

