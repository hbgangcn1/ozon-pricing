import React, { useEffect, useState } from 'react'
import { Table, Button, Modal, Form, Input, InputNumber, message } from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons'
import { productsAPI } from '../services/api'
import { useProductStore } from '../stores/productStore'

function ProductsPage() {
  const { products, setProducts, addProduct, updateProduct, removeProduct } = useProductStore()
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [editingProduct, setEditingProduct] = useState(null)
  const [deleteModalVisible, setDeleteModalVisible] = useState(false)
  const [pendingDelete, setPendingDelete] = useState(null)
  const [form] = Form.useForm()

  useEffect(() => {
    fetchProducts()
  }, [])

  const fetchProducts = async () => {
    setLoading(true)
    try {
      const response = await productsAPI.getAll()
      setProducts(response)
    } catch (error) {
      message.error('获取产品列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = () => {
    setEditingProduct(null)
    form.resetFields()
    setModalVisible(true)
  }

  const handleEdit = (record) => {
    setEditingProduct(record)
    form.setFieldsValue(record)
    setModalVisible(true)
  }

  const handleDelete = (record) => {
    setPendingDelete(record)
    setDeleteModalVisible(true)
  }

  const confirmDelete = async () => {
    if (!pendingDelete) return
    try {
      await productsAPI.delete(pendingDelete.id)
      removeProduct(pendingDelete.id)
      message.success('删除成功')
    } catch (error) {
      message.error('删除失败')
    } finally {
      setDeleteModalVisible(false)
      setPendingDelete(null)
    }
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (editingProduct) {
        const response = await productsAPI.update(editingProduct.id, values)
        updateProduct(editingProduct.id, response)
        message.success('更新成功')
      } else {
        const response = await productsAPI.create(values)
        addProduct(response)
        message.success('创建成功')
      }
      setModalVisible(false)
    } catch (error) {
      message.error('操作失败')
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '产品名称', dataIndex: 'name', key: 'name' },
    { title: '类别', dataIndex: 'category', key: 'category' },
    { title: '单价', dataIndex: 'unit_price', key: 'unit_price', render: (v) => v != null ? Number(v).toFixed(2) : '-' },
    { title: '重量(g)', dataIndex: 'weight_g', key: 'weight_g', render: (v) => v != null ? Number(v).toFixed(2) : '-' },
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
          <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record)}>
            删除
          </Button>
        </>
      ),
    },
  ]

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          添加产品
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={products}
        rowKey="id"
        loading={loading}
      />
      <Modal
        title={editingProduct ? '编辑产品' : '添加产品'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="产品名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="category" label="类别">
            <Input />
          </Form.Item>
          <Form.Item name="unit_price" label="单价">
            <InputNumber step={0.01} precision={2} />
          </Form.Item>
          <Form.Item name="weight_g" label="重量(g)">
            <InputNumber step={0.01} precision={2} />
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        title="确认删除"
        open={deleteModalVisible}
        onOk={confirmDelete}
        onCancel={() => {
          setDeleteModalVisible(false)
          setPendingDelete(null)
        }}
        okText="确定删除"
        cancelText="取消"
        okType="danger"
      >
        {pendingDelete && (
          <p>确定要删除产品「<strong>{pendingDelete.name}</strong>」吗？此操作不可恢复。</p>
        )}
      </Modal>
    </div>
  )
}

export default ProductsPage
