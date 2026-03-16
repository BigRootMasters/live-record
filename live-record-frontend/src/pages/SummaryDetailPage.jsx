import React, { useEffect, useState } from 'react'
import { Alert, Button, Card, Descriptions, Result, Space, Spin, Tag, message } from 'antd'
import { CopyOutlined, MessageOutlined } from '@ant-design/icons'
import { Link, useParams } from 'react-router-dom'

import { summaryAPI } from '../api'

const statusMeta = {
  pending: { color: 'default', text: '待处理' },
  processing: { color: 'processing', text: '转写中' },
  completed: { color: 'green', text: '已生成' },
  notified: { color: 'blue', text: '已通知' },
  failed: { color: 'red', text: '失败' }
}

function SummaryDetailPage() {
  const { summaryId } = useParams()
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    const fetchSummary = async () => {
      setLoading(true)
      setNotFound(false)
      try {
        const data = await summaryAPI.getSummary(summaryId)
        setSummary(data)
      } catch (error) {
        if (error?.response?.status === 404) {
          setNotFound(true)
        } else {
          message.error('获取文字稿详情失败')
        }
      } finally {
        setLoading(false)
      }
    }

    fetchSummary()
  }, [summaryId])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(summary?.content || '')
      message.success('文字稿已复制到剪贴板')
    } catch (error) {
      message.error('复制失败，请稍后重试')
    }
  }

  if (loading) {
    return <Spin spinning style={{ width: '100%', marginTop: 80 }} />
  }

  if (notFound) {
    return (
      <Result
        status="404"
        title="文字稿不存在"
        subTitle="该链接对应的文字稿未找到，可能尚未生成或已被删除。"
        extra={<Button type="primary"><Link to="/summaries">返回文字稿列表</Link></Button>}
      />
    )
  }

  const meta = statusMeta[summary?.status] || { color: 'default', text: summary?.status || '-' }

  return (
    <div className="summary-detail-page">
      <div className="page-header">
        <h1>文字稿详情</h1>
        <Space>
          <Button icon={<CopyOutlined />} onClick={handleCopy}>复制全文</Button>
          <Button><Link to="/summaries">返回列表</Link></Button>
        </Space>
      </div>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="这是供通知消息直接打开的文字稿页面"
        description="如果你是从企业微信机器人点进来的，这里会显示该场直播的完整转写内容。"
      />

      <Card bordered={false}>
        <Descriptions bordered column={2}>
          <Descriptions.Item label="主播">
            {summary?.recording?.anchor?.name || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={meta.color}>{meta.text}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="录制ID">{summary?.recording_id}</Descriptions.Item>
          <Descriptions.Item label="文字长度">{summary?.transcript_length || 0} 字</Descriptions.Item>
          <Descriptions.Item label="开始时间">
            {summary?.recording?.start_time ? new Date(summary.recording.start_time).toLocaleString() : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="结束时间">
            {summary?.recording?.end_time ? new Date(summary.recording.end_time).toLocaleString() : '-'}
          </Descriptions.Item>
        </Descriptions>

        <div style={{ marginTop: 20 }}>
          <Space style={{ marginBottom: 12 }}>
            <Tag icon={<MessageOutlined />}>企业微信通知对应全文</Tag>
          </Space>
          <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
            {summary?.content || '暂无文字稿内容'}
          </div>
        </div>
      </Card>
    </div>
  )
}

export default SummaryDetailPage
