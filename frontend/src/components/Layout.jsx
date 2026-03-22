import { Outlet, useNavigate } from 'react-router-dom'
import { Layout, Menu, Button } from 'antd'
import {
  DashboardOutlined,
  ShoppingOutlined,
  CarOutlined,
  DollarOutlined,
  LogoutOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '../stores/authStore'

const { Header, Content } = Layout

function LayoutComponent() {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()

  const menuItems = [
    { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
    { key: '/products', icon: <ShoppingOutlined />, label: '产品管理' },
    { key: '/logistics', icon: <CarOutlined />, label: '物流规则' },
    { key: '/pricing', icon: <DollarOutlined />, label: '定价计算' },
  ]

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ color: 'white', fontSize: 18, fontWeight: 'bold' }}>
          物流定价系统
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ color: 'rgba(255,255,255,0.65)' }}>
            {user?.username || '用户'}
          </span>
          <Button
            type="text"
            icon={<LogoutOutlined />}
            onClick={handleLogout}
            style={{ color: 'white' }}
          >
            退出
          </Button>
        </div>
      </Header>
      <Layout>
        <Menu
          mode="horizontal"
          selectedKeys={[location.pathname]}
          onClick={({ key }) => navigate(key)}
          items={menuItems}
          style={{ flex: 1 }}
        />
        <Content style={{ padding: 24 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default LayoutComponent
