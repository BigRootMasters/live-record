import React, { useState, useEffect } from 'react'
import { Table, Button, Space, Tag, Popconfirm, message, DatePicker, Input, Spin } from 'antd'
import { DeleteOutlined, PlayCircleOutlined, FileTextOutlined } from '@ant-design/icons'
import { recordingAPI } from '../api'

const { Column } = Table
const { RangePicker } = DatePicker
const { Search } = Input

const RecordingList = () => {
  const [recordings, setRecordings] = useState([])
  const [loading, setLoading] = useState(false)

  // 获取录制记录
  useEffect(() => {
    fetchRecordings()
  }, [])

  const fetchRecordings = async () => {
    setLoading(true)
    try {
      const data = await recordingAPI.getRecordings()
      setRecordings(data)
    } catch (error) {
      message.error('获取录制记录失败')
      console.error('获取录制记录失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'recording':
        return 'blue'
      case 'completed':
        return 'green'
      case 'failed':
        return 'red'
      default:
        return 'default'
    }
  }

  const getStatusText = (status) => {
    switch (status) {
      case 'recording':
        return '录制中'
      case 'completed':
        return '已完成'
      case 'failed':
        return '失败'
      default:
        return status
    }
  }

  return (
    <div className="recording-list">
      <div className="page-header">
        <h1>录制记录</h1>
        <div className="search-filters">
          <Search placeholder="搜索主播名称" style={{ width: 200, marginRight: 16 }} />
          <RangePicker style={{ marginRight: 16 }} />
          <Button type="default">筛选</Button>
        </div>
      </div>
      <Spin spinning={loading}>
        <Table dataSource={recordings} rowKey="id">
          <Column title="ID" dataIndex="id" key="id" />
          <Column 
            title="主播名称" 
            key="anchorName"
            render={(record) => record.anchor ? record.anchor.name : '-'} 
          />
          <Column title="开始时间" dataIndex="start_time" key="start_time" />
          <Column title="结束时间" dataIndex="end_time" key="end_time" />
          <Column title="录制时长" dataIndex="video_duration" key="video_duration" />
          <Column 
            title="状态" 
            dataIndex="status" 
            key="status"
            render={(status) => (
              <Tag color={getStatusColor(status)}>
                {getStatusText(status)}
              </Tag>
            )}
          />
          <Column title="视频路径" dataIndex="video_path" key="video_path" ellipsis />
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
                {record.status === 'completed' && (
                  <>
                    <Button icon={<PlayCircleOutlined />}>
                      播放
                    </Button>
                    <Button icon={<FileTextOutlined />}>
                      查看摘要
                    </Button>
                  </>
                )}
              </Space>
            )}
          />
        </Table>
      </Spin>
    </div>
  )
}

export default RecordingList