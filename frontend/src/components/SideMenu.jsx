import { useState } from 'react'
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
