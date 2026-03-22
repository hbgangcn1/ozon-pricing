import { useEffect, useState } from 'react'
import { Table, Button, Modal, Form, Input, InputNumber, Select, message, Popconfirm } from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons'
import { logisticsAPI } from '../services/api'
import { useLogisticsStore } from '../stores/logisticsStore'

function LogisticsPage() {
  const { logistics, setLogistics, addLogistics, updateLogistics, removeLogistics } = useLogisticsStore()
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [form] = Form.useForm()

  useEffect(() => {
    fetchLogistics()
  }, [])

  const fetchLogistics = async () => {
    setLoading(true)
    try {
      const response = await logisticsAPI.getAll()
      setLogistics(response.data)
    } catch (error) {
      message.error('获取物流规则列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = () => {
    setEditingItem(null)
    form.resetFields()
    setModalVisible(true)
  }

  const handleEdit = (record) => {
    setEditingItem(record)
    form.setFieldsValue(record)
    setModalVisible(true)
  }

  const handleDelete = async (id) => {
    try {
      await logisticsAPI.delete(id)
      removeLogistics(id)
      message.success('删除成功')
    } catch (error) {
      message.error('删除失败')
    }
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (editingItem) {
        const response = await logisticsAPI.update(editingItem.id, values)
        updateLogistics(editingItem.id, response.data)
        message.success('更新成功')
      } else {
        const response = await logisticsAPI.create(values)
        addLogistics(response.data)
        message.success('创建成功')
      }
      setModalVisible(false)
    } catch (error) {
      message.error('操作失败')
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '类型', dataIndex: 'type', key: 'type' },
    { title: '基础费用', dataIndex: 'base_fee', key: 'base_fee' },
    { title: '重量系数', dataIndex: 'weight_factor', key: 'weight_factor' },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_, record) => (
        <>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确认删除?"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </>
      ),
    },
  ]

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          添加物流规则
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={logistics}
        rowKey="id"
        loading={loading}
      />
      <Modal
        title={editingItem ? '编辑物流规则' : '添加物流规则'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="type" label="类型">
            <Select>
              <Select.Option value="standard">标准</Select.Option>
              <Select.Option value="land">陆运</Select.Option>
              <Select.Option value="air">空运</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="base_fee" label="基础费用">
            <InputNumber step={0.01} />
          </Form.Item>
          <Form.Item name="weight_factor" label="重量系数">
            <InputNumber step={0.01} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default LogisticsPage
