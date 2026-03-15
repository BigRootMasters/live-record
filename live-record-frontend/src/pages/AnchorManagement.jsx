import React, { useEffect, useState } from 'react'
import { Alert, Card, Space, Spin, Switch, Table, Tag, message } from 'antd'

import { anchorAPI } from '../api'

const columns = [
  {
    title: '主播名称',
    dataIndex: 'name',
    key: 'name'
  },
  {
    title: '抖音 ID',
    dataIndex: 'douyin_id',
    key: 'douyin_id'
  },
  {
    title: '固定身份',
    key: 'config',
    render: (_, record) => (
      <Space direction="vertical" size={2}>
        <span>anchor_id: {record.config?.anchor_id || '-'}</span>
        <span>profile_url: {record.config?.profile_url || '-'}</span>
      </Space>
    )
  },
  {
    title: '关注状态',
    dataIndex: 'is_followed',
    key: 'is_followed',
    render: (value) => <Switch checked={value} disabled />
  },
  {
    title: '说明',
    key: 'notes',
    render: (_, record) =>
      record.config?.notes ? <Tag color="default">{record.config.notes}</Tag> : '-'
  }
]

const AnchorManagement = () => {
  const [anchors, setAnchors] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const fetchAnchors = async () => {
      setLoading(true)
      try {
        const data = await anchorAPI.getAnchors()
        setAnchors(data.items || [])
      } catch (error) {
        message.error('获取主播列表失败')
        console.error('获取主播列表失败:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchAnchors()
  }, [])

  return (
    <div className="anchor-management">
      <div className="page-header">
        <h1>主播配置</h1>
      </div>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="主播信息当前由 backend/config/anchors.json 管理"
        description="页面只用于查看同步结果。需要新增或修改主播时，请更新配置文件并重启后端服务。"
      />
      <Spin spinning={loading}>
        <Card bordered={false}>
          <Table dataSource={anchors} columns={columns} rowKey="id" pagination={false} />
        </Card>
      </Spin>
    </div>
  )
}

export default AnchorManagement
