import { Outlet } from 'react-router-dom'
import { Layout } from 'antd'
import SideMenu from './SideMenu'
import TopHeader from './TopHeader'

const { Content } = Layout

function LayoutComponent() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <SideMenu />
      <Layout style={{ marginLeft: 220, transition: 'margin-left 0.2s' }}>
        <TopHeader />
        <Content
          style={{
            margin: 24,
            padding: 24,
            background: '#fff',
            borderRadius: 8,
            minHeight: 280,
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default LayoutComponent
