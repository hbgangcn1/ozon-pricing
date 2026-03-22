import { useEffect, useState } from 'react'
import { Card, Row, Col, Statistic } from 'antd'
import { ShoppingOutlined, CarOutlined, DollarOutlined, UserOutlined } from 'antd'
import { productsAPI, logisticsAPI } from '../services/api'

function DashboardPage() {
  const [stats, setStats] = useState({
    products: 0,
    logistics: 0,
    loading: true,
  })

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [productsRes, logisticsRes] = await Promise.all([
          productsAPI.getAll(),
          logisticsAPI.getAll(),
        ])
        setStats({
          products: productsRes.data.length,
          logistics: logisticsRes.data.length,
          loading: false,
        })
      } catch (error) {
        console.error('获取数据失败:', error)
        setStats((prev) => ({ ...prev, loading: false }))
      }
    }
    fetchData()
  }, [])

  return (
    <div>
      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic
              title="产品数量"
              value={stats.products}
              prefix={<ShoppingOutlined />}
              loading={stats.loading}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="物流规则"
              value={stats.logistics}
              prefix={<CarOutlined />}
              loading={stats.loading}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="用户角色"
              value="管理员"
              prefix={<UserOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="系统状态"
              value="正常"
              prefix={<DollarOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default DashboardPage
