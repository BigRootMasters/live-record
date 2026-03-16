import React, { useEffect, useState } from 'react'
import { Button, Descriptions, Input, message, Modal, Space, Spin, Table, Tag } from 'antd'
import { CopyOutlined, MessageOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { summaryAPI } from '../api'

const { Search } = Input

const statusMeta = {
  pending: { color: 'default', text: '待处理' },
  processing: { color: 'processing', text: '转写中' },
  completed: { color: 'green', text: '已生成' },
  notified: { color: 'blue', text: '已通知' },
  failed: { color: 'red', text: '失败' }
}

const SummaryList = () => {
  const [summaries, setSummaries] = useState([])
  const [filteredSummaries, setFilteredSummaries] = useState([])
  const [selectedSummary, setSelectedSummary] = useState(null)
  const [isModalVisible, setIsModalVisible] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchSummaries()
  }, [])

  const fetchSummaries = async () => {
    setLoading(true)
    try {
      const data = await summaryAPI.getSummaries()
      const items = data.items || []
      setSummaries(items)
      setFilteredSummaries(items)
    } catch (error) {
      message.error('获取文字稿列表失败')
      console.error('获取文字稿列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const showSummaryDetail = async (summary) => {
    try {
      const detail = await summaryAPI.getSummary(summary.id)
      setSelectedSummary(detail)
      setIsModalVisible(true)
    } catch (error) {
      message.error('获取文字稿详情失败')
    }
  }

  const handleSearch = (value) => {
    const keyword = value.trim().toLowerCase()
    if (!keyword) {
      setFilteredSummaries(summaries)
      return
    }

    setFilteredSummaries(
      summaries.filter((item) => {
        const anchorName = item.recording?.anchor?.name?.toLowerCase() || ''
        const content = item.content_preview?.toLowerCase() || ''
        return anchorName.includes(keyword) || content.includes(keyword)
      })
    )
  }

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text || '')
    message.success('文字稿已复制到剪贴板')
  }

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80
    },
    {
      title: '主播名称',
      key: 'anchorName',
      render: (_, record) => record.recording?.anchor?.name || '-'
    },
    {
      title: '文字长度',
      dataIndex: 'transcript_length',
      key: 'transcript_length',
      render: (value) => `${value || 0} 字`
    },
    {
      title: '内容预览',
      dataIndex: 'content_preview',
      key: 'content_preview',
      ellipsis: true
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => {
        const meta = statusMeta[status] || { color: 'default', text: status }
        return <Tag color={meta.color}>{meta.text}</Tag>
      }
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (value) => value ? new Date(value).toLocaleString() : '-'
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Button onClick={() => showSummaryDetail(record)}>查看全文</Button>
          <Button type="link">
            <Link to={`/summaries/${record.id}`}>打开详情页</Link>
          </Button>
        </Space>
      )
    }
  ]

  return (
    <div className="summary-list">
      <div className="page-header">
        <h1>文字稿</h1>
        <div className="search-filters">
          <Search
            placeholder="搜索主播名称或内容"
            style={{ width: 280 }}
            onSearch={handleSearch}
            allowClear
          />
        </div>
      </div>
      <Spin spinning={loading}>
        <Table dataSource={filteredSummaries} columns={columns} rowKey="id" />
      </Spin>

      <Modal
        title={`文字稿详情 - ID: ${selectedSummary?.id}`}
        open={isModalVisible}
        onCancel={() => {
          setIsModalVisible(false)
          setSelectedSummary(null)
        }}
        footer={[
          <Button key="copy" icon={<CopyOutlined />} onClick={() => handleCopy(selectedSummary?.content)}>
            复制全文
          </Button>,
          <Button key="close" onClick={() => setIsModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={900}
      >
        {selectedSummary && (
          <div>
            <Descriptions bordered column={2}>
              <Descriptions.Item label="主播">
                {selectedSummary.recording?.anchor?.name || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={(statusMeta[selectedSummary.status] || {}).color || 'default'}>
                  {(statusMeta[selectedSummary.status] || {}).text || selectedSummary.status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="录制ID">{selectedSummary.recording_id}</Descriptions.Item>
              <Descriptions.Item label="文字长度">{selectedSummary.transcript_length || 0} 字</Descriptions.Item>
              <Descriptions.Item label="开始时间">
                {selectedSummary.recording?.start_time ? new Date(selectedSummary.recording.start_time).toLocaleString() : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="结束时间">
                {selectedSummary.recording?.end_time ? new Date(selectedSummary.recording.end_time).toLocaleString() : '-'}
              </Descriptions.Item>
            </Descriptions>

            <div style={{ marginTop: 20 }}>
              <Space style={{ marginBottom: 12 }}>
                <Tag icon={<MessageOutlined />}>可由企业微信机器人发送通知</Tag>
              </Space>
              <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
                {selectedSummary.content || '暂无文字稿内容'}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

export default SummaryList
