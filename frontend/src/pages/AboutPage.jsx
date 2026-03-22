import { Card, Typography, Descriptions } from 'antd'

const { Title } = Typography

function AboutPage() {
  return (
    <div>
      <Title level={4}>ℹ️ 关于我们</Title>
      <Card title="🏢 公司信息">
        <Descriptions column={1} bordered>
          <Descriptions.Item label="公司名称">深圳超凡酷玩电子商务有限公司</Descriptions.Item>
          <Descriptions.Item label="主营业务">中俄、中美跨境电商（Ozon、亚马逊、eBay、沃尔玛），同时为跨境卖家提供专业的物流定价解决方案</Descriptions.Item>
          <Descriptions.Item label="办公地址">广东省深圳市龙岗区平湖街道平湖社区平安大道一号华南城铁东物流区14栋219</Descriptions.Item>
          <Descriptions.Item label="联系电话">19328702460</Descriptions.Item>
        </Descriptions>
      </Card>
      <Card title="🚀 业务简介" style={{ marginTop: 16 }}>
        <p>我们是一家专注于跨境电商服务的公司，致力于为跨境卖家提供专业的物流定价解决方案。</p>
        <p>通过智能化的定价系统，帮助卖家快速准确地计算物流成本，优化定价策略，提升竞争力。</p>
      </Card>
    </div>
  )
}

export default AboutPage
