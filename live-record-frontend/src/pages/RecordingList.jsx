import React, { useEffect, useState } from 'react'
import { Button, message, Space, Spin, Table, Tag } from 'antd'
import { FileTextOutlined } from '@ant-design/icons'

import { recordingAPI } from '../api'

const statusMeta = {
  recording: { color: 'blue', text: '录制中' },
  completed: { color: 'green', text: '待转写' },
  transcribing: { color: 'processing', text: '转写中' },
  transcribed: { color: 'cyan', text: '已转写' },
  notified: { color: 'cyan', text: '已通知' },
  transcription_failed: { color: 'red', text: '转写失败' },
  failed: { color: 'red', text: '失败' }
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
    render: (_, record) => record.anchor?.name || '-'
  },
  {
    title: '开始时间',
    dataIndex: 'start_time',
    key: 'start_time',
    render: (value) => value ? new Date(value).toLocaleString() : '-'
  },
  {
    title: '结束时间',
    dataIndex: 'end_time',
    key: 'end_time',
    render: (value) => value ? new Date(value).toLocaleString() : '-'
  },
  {
    title: '录制时长',
    dataIndex: 'video_duration',
    key: 'video_duration',
    render: (value) => value ? `${value} 秒` : '-'
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
    title: '文件路径',
    dataIndex: 'video_path',
    key: 'video_path',
    ellipsis: true
  },
  {
    title: '操作',
    key: 'action',
    render: (_, record) => (
      <Space size="middle">
        {(record.status === 'transcribed' || record.status === 'notified') && (
          <Button icon={<FileTextOutlined />} disabled>
            文字稿已生成
          </Button>
        )}
      </Space>
    )
  }
]

const RecordingList = () => {
  const [recordings, setRecordings] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const fetchRecordings = async () => {
      setLoading(true)
      try {
        const data = await recordingAPI.getRecordings()
        setRecordings(data.items || [])
      } catch (error) {
        message.error('获取录制记录失败')
        console.error('获取录制记录失败:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchRecordings()
  }, [])

  return (
    <div className="recording-list">
      <div className="page-header">
        <h1>录制记录</h1>
      </div>
      <Spin spinning={loading}>
        <Table dataSource={recordings} columns={columns} rowKey="id" />
      </Spin>
    </div>
  )
}

export default RecordingList
