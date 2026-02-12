import React, { useState, useEffect } from 'react'
import { Table, Button, Space, Tag, Popconfirm, message, DatePicker, Input, Modal, Descriptions, Spin } from 'antd'
import { DeleteOutlined, MailOutlined, MessageOutlined, CopyOutlined } from '@ant-design/icons'
import { summaryAPI } from '../api'

const { Column } = Table
const { RangePicker } = DatePicker
const { Search } = Input

const SummaryList = () => {
  const [summaries, setSummaries] = useState([])
  const [selectedSummary, setSelectedSummary] = useState(null)
  const [isModalVisible, setIsModalVisible] = useState(false)
  const [loading, setLoading] = useState(false)

  // 获取摘要列表
  useEffect(() => {
    fetchSummaries()
  }, [])

  const fetchSummaries = async () => {
    setLoading(true)
    try {
      const data = await summaryAPI.getSummaries()
      setSummaries(data)
    } catch (error) {
      message.error('获取摘要列表失败')
      console.error('获取摘要列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const showSummaryDetail = (summary) => {
    setSelectedSummary(summary)
    setIsModalVisible(true)
  }

  const handleCancel = () => {
    setIsModalVisible(false)
    setSelectedSummary(null)
  }

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text)
    message.success('内容已复制到剪贴板')
  }

  return (
    <div className="summary-list">
      <div className="page-header">
        <h1>内容摘要</h1>
        <div className="search-filters">
          <Search placeholder="搜索主播名称" style={{ width: 200, marginRight: 16 }} />
          <RangePicker style={{ marginRight: 16 }} />
          <Button type="default">筛选</Button>
        </div>
      </div>
      <Spin spinning={loading}>
        <Table dataSource={summaries} rowKey="id">
          <Column title="ID" dataIndex="id" key="id" />
          <Column 
            title="主播名称" 
            key="anchorName"
            render={(record) => record.recording && record.recording.anchor ? record.recording.anchor.name : '-'} 
          />
          <Column title="内容" dataIndex="content" key="content" ellipsis />
          <Column 
            title="核心观点" 
            dataIndex="core_points" 
            key="core_points"
            render={(corePoints) => (
              <div>
                {corePoints && corePoints.map((point, index) => (
                  <div key={index} style={{ marginBottom: 4 }}>
                    • {point}
                  </div>
                ))}
              </div>
            )}
          />
          <Column 
            title="状态" 
            dataIndex="status" 
            key="status"
            render={(status) => (
              <Tag color={status === 'completed' ? 'green' : 'blue'}>
                {status === 'completed' ? '已完成' : '生成中'}
              </Tag>
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
                <Button onClick={() => showSummaryDetail(record)}>
                  查看详情
                </Button>
                <Button icon={<MailOutlined />}>
                  发送邮件
                </Button>
                <Button icon={<MessageOutlined />}>
                  发送微信
                </Button>
              </Space>
            )}
          />
        </Table>
      </Spin>

      <Modal
        title={`摘要详情 - ID: ${selectedSummary?.id}`}
        open={isModalVisible}
        onCancel={handleCancel}
        footer={[
          <Button key="cancel" onClick={handleCancel}>
            关闭
          </Button>,
          <Button key="copy" icon={<CopyOutlined />} onClick={() => handleCopy(selectedSummary?.content)}>
            复制内容
          </Button>,
          <Button key="email" icon={<MailOutlined />} type="primary">
            发送邮件
          </Button>
        ]}
        width={800}
      >
        {selectedSummary && (
          <div>
            <Descriptions bordered>
              <Descriptions.Item label="录制ID">{selectedSummary.recording_id}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={selectedSummary.status === 'completed' ? 'green' : 'blue'}>
                  {selectedSummary.status === 'completed' ? '已完成' : '生成中'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {selectedSummary.created_at ? new Date(selectedSummary.created_at).toLocaleString() : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="更新时间">
                {selectedSummary.updated_at ? new Date(selectedSummary.updated_at).toLocaleString() : '-'}
              </Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: 20 }}>
              <h3>核心观点</h3>
              <ul style={{ marginLeft: 20 }}>
                {selectedSummary.core_points && selectedSummary.core_points.map((point, index) => (
                  <li key={index} style={{ marginBottom: 8 }}>{point}</li>
                ))}
              </ul>
            </div>
            <div style={{ marginTop: 20 }}>
              <h3>详细摘要</h3>
              <div style={{ lineHeight: 1.8 }}>{selectedSummary.content}</div>
            </div>
            {selectedSummary.market_analysis && (
              <div style={{ marginTop: 20 }}>
                <h3>市场分析</h3>
                <div style={{ lineHeight: 1.8 }}>{selectedSummary.market_analysis}</div>
              </div>
            )}
            {selectedSummary.investment_advice && (
              <div style={{ marginTop: 20 }}>
                <h3>投资建议</h3>
                <div style={{ lineHeight: 1.8 }}>{selectedSummary.investment_advice}</div>
              </div>
            )}
            {selectedSummary.keywords && (
              <div style={{ marginTop: 20 }}>
                <h3>关键词</h3>
                <Space wrap>
                  {selectedSummary.keywords.map((keyword, index) => (
                    <Tag key={index}>{keyword}</Tag>
                  ))}
                </Space>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}

export default SummaryList