import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import {
  DollarOutlined,
  CarOutlined,
  KeyOutlined,
  CrownOutlined,
  CreditCardOutlined,
  SettingOutlined,
  TeamOutlined,
  GiftOutlined,
  BarChartOutlined,
  InfoCircleOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '../stores/authStore'
import apiClient from '../services/api'

function ExchangeRateWidget({ collapsed }) {
  const [rates, setRates] = useState({
    'RUB/CNY': null,
    'CNY/RUB': null,
    'USD/CNY': null,
    'CNY/USD': null,
  })
  const [loading, setLoading] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)

  const fetchRates = async () => {
    setLoading(true)
    try {
      const data = await apiClient.get('/exchange/rates')
      setRates(data)
      setLastUpdated(new Date())
    } catch (error) {
      console.error('获取汇率失败:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    fetchRates()
    const interval = setInterval(fetchRates, 5 * 60 * 1000) // 5分钟
    return () => {
      controller.abort()
      clearInterval(interval)
    }
  }, [])

  if (collapsed) {
    return (
      <div
        style={{
          padding: '16px 8px',
          textAlign: 'center',
          color: 'rgba(255,255,255,0.65)',
          fontSize: 12,
        }}
      >
        汇率
      </div>
    )
  }

  return (
    <div
      style={{
        padding: '16px',
        borderTop: '1px solid rgba(255,255,255,0.1)',
        borderBottom: '1px solid rgba(255,255,255,0.1)',
      }}
    >
      <div
        style={{
          color: 'rgba(255,255,255,0.85)',
          fontSize: 14,
          fontWeight: 'bold',
          marginBottom: 12,
        }}
      >
        实时汇率
      </div>
      <table style={{ width: '100%', color: 'rgba(255,255,255,0.85)', fontSize: 12 }}>
        <tbody>
          {Object.entries(rates).map(([pair, value]) => (
            <tr key={pair}>
              <td style={{ padding: '4px 0' }}>{pair}</td>
              <td style={{ padding: '4px 0', textAlign: 'right' }}>
                {value !== null ? value.toFixed(4) : '-'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div
        style={{
          marginTop: 12,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: 10,
          color: 'rgba(255,255,255,0.45)',
        }}
      >
        <span>
          {lastUpdated
            ? `更新: ${lastUpdated.toLocaleTimeString()}`
            : '未更新'}
        </span>
        <button
          onClick={fetchRates}
          disabled={loading}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'rgba(255,255,255,0.65)',
            cursor: 'pointer',
            padding: '2px 6px',
          }}
        >
          {loading ? '刷新中...' : '刷新'}
        </button>
      </div>
    </div>
  )
}

const { Sider } = Layout

const adminMenuItems = [
  { key: '/pricing', icon: <DollarOutlined />, label: '💰 定价计算' },
  { key: '/logistics', icon: <CarOutlined />, label: '🚚 物流管理' },
  { key: '/account', icon: <KeyOutlined />, label: '🔐 账户管理' },
  { key: '/subscription', icon: <CrownOutlined />, label: '💎 订阅管理' },
  { key: '/payment', icon: <CreditCardOutlined />, label: '💳 支付中心' },
  { key: '/settings', icon: <SettingOutlined />, label: '⚙️ 系统设置' },
  { key: '/users', icon: <TeamOutlined />, label: '👥 用户管理' },
  { key: '/plans', icon: <GiftOutlined />, label: '🎁 套餐管理' },
  { key: '/statistics', icon: <BarChartOutlined />, label: '📈 数据统计' },
  { key: '/about', icon: <InfoCircleOutlined />, label: 'ℹ️ 关于我们' },
]

const userMenuItems = adminMenuItems.filter(item =>
  ['/pricing', '/logistics', '/account', '/subscription', '/payment', '/about'].includes(item.key)
)

function SideMenu() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuthStore()

  const menuItems = user?.role === 'admin' ? adminMenuItems : userMenuItems

  const selectedKey = location.pathname === '/'
    ? '/pricing'
    : menuItems.find(item => location.pathname.startsWith(item.key))?.key || '/pricing'

  const handleMenuClick = ({ key }) => {
    navigate(key)
  }

  return (
    <Sider
      trigger={null}
      collapsible
      collapsed={collapsed}
      width={220}
      style={{
        overflow: 'auto',
        height: '100vh',
        position: 'fixed',
        left: 0,
        top: 0,
        bottom: 0,
        background: '#001529',
      }}
    >
      <div
        style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          padding: collapsed ? 0 : '0 16px',
          color: 'white',
          fontSize: 16,
          fontWeight: 'bold',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
        }}
      >
        {collapsed ? '📦' : '📦 物流定价'}
      </div>

      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[selectedKey]}
        onClick={handleMenuClick}
        items={menuItems}
        style={{ borderRight: 0, marginTop: 8 }}
      />

      <ExchangeRateWidget collapsed={collapsed} />

      <div
        onClick={() => setCollapsed(!collapsed)}
        style={{
          position: 'absolute',
          bottom: 16,
          left: 0,
          right: 0,
          display: 'flex',
          justifyContent: 'center',
          cursor: 'pointer',
          color: 'rgba(255,255,255,0.65)',
          padding: '8px 0',
        }}
      >
        {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
      </div>
    </Sider>
  )
}

export default SideMenu
