import { useEffect, useState } from 'react'
import { Card, Form, Select, Button, Result, message } from 'antd'
import { pricingAPI, productsAPI, logisticsAPI } from '../services/api'

function PricingPage() {
  const [products, setProducts] = useState([])
  const [logistics, setLogistics] = useState([])
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [form] = Form.useForm()

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [productsRes, logisticsRes] = await Promise.all([
          productsAPI.getAll(),
          logisticsAPI.getAll(),
        ])
        setProducts(productsRes.data)
        setLogistics(logisticsRes.data)
      } catch (error) {
        message.error('获取数据失败')
      }
    }
    fetchData()
  }, [])

  const handleCalculate = async (values) => {
    setLoading(true)
    setResult(null)
    try {
      const response = await pricingAPI.calculate(
        values.product_id,
        values.logistics_id,
        values.mode || 'fast'
      )
      setResult(response.data)
    } catch (error) {
      message.error('计算失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <Card title="定价计算" style={{ marginBottom: 24 }}>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCalculate}
        >
          <Form.Item
            name="product_id"
            label="选择产品"
            rules={[{ required: true, message: '请选择产品' }]}
          >
            <Select placeholder="请选择产品">
              {products.map((p) => (
                <Select.Option key={p.id} value={p.id}>
                  {p.name} - ¥{p.unit_price}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="logistics_id"
            label="选择物流"
            rules={[{ required: true, message: '请选择物流' }]}
          >
            <Select placeholder="请选择物流">
              {logistics.map((l) => (
                <Select.Option key={l.id} value={l.id}>
                  {l.name} ({l.type})
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item name="mode" label="计算模式" initialValue="fast">
            <Select>
              <Select.Option value="fast">快速</Select.Option>
              <Select.Option value="detailed">详细</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading}>
              计算
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {result && (
        <Card title="计算结果">
          <Result
            title={`最终价格: ¥${result.final_price?.toFixed(2) || 0}`}
            subTitle={
              <div>
                <p>物流成本: ¥{result.logistics_cost?.toFixed(2) || 0}</p>
                <p>货币: {result.currency}</p>
                <p>汇率: {result.exchange_rate}</p>
                <p>计算模式: {result.calculation_mode}</p>
              </div>
            }
          />
        </Card>
      )}
    </div>
  )
}

export default PricingPage
