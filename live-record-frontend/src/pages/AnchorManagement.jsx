import React, { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, Switch, message, Space, Popconfirm, Spin } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { anchorAPI } from '../api'

const { Column } = Table

const AnchorManagement = () => {
  const [form] = Form.useForm()
  const [isModalVisible, setIsModalVisible] = useState(false)
  const [editingRecord, setEditingRecord] = useState(null)
  const [anchors, setAnchors] = useState([])
  const [loading, setLoading] = useState(false)

  // 获取主播列表
  useEffect(() => {
    fetchAnchors()
  }, [])

  const fetchAnchors = async () => {
    setLoading(true)
    try {
      const data = await anchorAPI.getAnchors()
      setAnchors(data)
    } catch (error) {
      message.error('获取主播列表失败')
      console.error('获取主播列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const showModal = (record = null) => {
    setEditingRecord(record)
    if (record) {
      form.setFieldsValue({
        name: record.name,
        douyinId: record.douyin_id,
        roomId: record.room_id,
        avatarUrl: record.avatar_url,
        isFollowed: record.is_followed
      })
    } else {
      form.resetFields()
    }
    setIsModalVisible(true)
  }

  const handleCancel = () => {
    setIsModalVisible(false)
    setEditingRecord(null)
    form.resetFields()
  }

  const handleOk = async (values) => {
    setLoading(true)
    try {
      if (editingRecord) {
        // 更新主播
        const updateData = {
          name: values.name,
          room_id: values.roomId,
          avatar_url: values.avatarUrl,
          is_followed: values.isFollowed
        }
        await anchorAPI.updateAnchor(editingRecord.id, updateData)
        message.success('主播信息更新成功')
      } else {
        // 添加新主播
        const newData = {
          name: values.name,
          douyin_id: values.douyinId,
          room_id: values.roomId,
          avatar_url: values.avatarUrl,
          is_followed: values.isFollowed
        }
        await anchorAPI.addAnchor(newData)
        message.success('主播添加成功')
      }
      // 重新获取主播列表
      await fetchAnchors()
      setIsModalVisible(false)
      setEditingRecord(null)
      form.resetFields()
    } catch (error) {
      message.error('操作失败，请重试')
      console.error('操作失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id) => {
    setLoading(true)
    try {
      await anchorAPI.deleteAnchor(id)
      message.success('主播删除成功')
      // 重新获取主播列表
      await fetchAnchors()
    } catch (error) {
      message.error('删除失败，请重试')
      console.error('删除失败:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="anchor-management">
      <div className="page-header">
        <h1>主播管理</h1>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => showModal()}>
          添加主播
        </Button>
      </div>
      <Spin spinning={loading}>
        <Table dataSource={anchors} rowKey="id">
          <Column title="ID" dataIndex="id" key="id" />
          <Column title="主播名称" dataIndex="name" key="name" />
          <Column title="抖音ID" dataIndex="douyin_id" key="douyin_id" />
          <Column title="直播间ID" dataIndex="room_id" key="room_id" />
          <Column title="头像URL" dataIndex="avatar_url" key="avatar_url" ellipsis />
          <Column 
            title="关注状态" 
            dataIndex="is_followed" 
            key="is_followed"
            render={(isFollowed) => (
              <Switch checked={isFollowed} />
            )}
          />
          <Column 
            title="创建时间" 
            dataIndex="created_at" 
            key="created_at"
            render={(createdAt) => {
              if (!createdAt) return '-';
              return new Date(createdAt).toLocaleString();
            }}
          />
          <Column 
            title="更新时间" 
            dataIndex="updated_at" 
            key="updated_at"
            render={(updatedAt) => {
              if (!updatedAt) return '-';
              return new Date(updatedAt).toLocaleString();
            }}
          />
          <Column 
            title="操作" 
            key="action"
            render={(_, record) => (
              <Space size="middle">
                <Button icon={<EditOutlined />} onClick={() => showModal(record)}>
                  编辑
                </Button>
                <Popconfirm
                  title="确定要删除这个主播吗？"
                  onConfirm={() => handleDelete(record.id)}
                  okText="确定"
                  cancelText="取消"
                >
                  <Button danger icon={<DeleteOutlined />}>
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            )}
          />
        </Table>
      </Spin>

      <Modal
        title={editingRecord ? "编辑主播" : "添加主播"}
        open={isModalVisible}
        onOk={form.submit}
        onCancel={handleCancel}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleOk}
        >
          <Form.Item
            name="name"
            label="主播名称"
            rules={[{ required: true, message: '请输入主播名称' }]}
          >
            <Input placeholder="请输入主播名称" />
          </Form.Item>
          <Form.Item
            name="douyinId"
            label="抖音ID"
            rules={[{ required: true, message: '请输入抖音ID' }]}
          >
            <Input placeholder="请输入抖音ID" />
          </Form.Item>
          <Form.Item
            name="roomId"
            label="直播间ID"
          >
            <Input placeholder="请输入直播间ID" />
          </Form.Item>
          <Form.Item
            name="avatarUrl"
            label="头像URL"
          >
            <Input placeholder="请输入头像URL" />
          </Form.Item>
          <Form.Item
            name="isFollowed"
            label="关注状态"
            valuePropName="checked"
            initialValue={true}
          >
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default AnchorManagement