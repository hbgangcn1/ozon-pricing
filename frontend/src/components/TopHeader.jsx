import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Layout, Button, Space, Tag } from 'antd'
import { LogoutOutlined, AimOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useAuthStore } from '../stores/authStore'

const { Header } = Layout

function TopHeader() {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const [mode, setMode] = useState('precise') // 'precise' | 'fast'

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const toggleMode = () => {
    setMode(prev => prev === 'precise' ? 'fast' : 'precise')
  }

  const getModeButton = () => {
    if (mode === 'precise') {
      return (
        <Button
          icon={<AimOutlined />}
          onClick={toggleMode}
          style={{ fontWeight: 'bold' }}
        >
          🎯 精准模式
        </Button>
      )
    }
    return (
      <Button
        icon={<ThunderboltOutlined />}
        onClick={toggleMode}
        type="primary"
        style={{ fontWeight: 'bold' }}
      >
        🚀 极速模式
      </Button>
    )
  }

  return (
    <Header
      style={{
        padding: '0 24px',
        background: '#fff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid #f0f0f0',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {getModeButton()}
        <span style={{ color: '#888', fontSize: 12 }}>
          {mode === 'precise' ? '完整参数定价' : '简化输入'}
        </span>
      </div>

      <Space size={16}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {user?.role === 'admin' && (
            <Tag color="blue" style={{ marginRight: 4 }}>管理员</Tag>
          )}
          <span style={{ color: '#333' }}>
            {user?.username || '用户'} 欢迎回来！
          </span>
        </div>
        <Button
          icon={<LogoutOutlined />}
          onClick={handleLogout}
        >
          退出
        </Button>
      </Space>
    </Header>
  )
}

export default TopHeader
