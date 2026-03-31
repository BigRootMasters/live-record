import React, { useEffect, useState } from 'react'
import { Alert, Card, Row, Col, Statistic, Progress, List, Tag } from 'antd'
import { UserOutlined, VideoCameraOutlined, FileTextOutlined, CheckCircleOutlined, ClockCircleOutlined, AlertOutlined } from '@ant-design/icons'
import { summaryAPI, systemAPI } from '../api'

function HomePage() {
  const [systemStatus, setSystemStatus] = useState(null)
  const [recentSummaries, setRecentSummaries] = useState([])
  const transcriptionEnabled = Boolean(systemStatus?.features?.transcription_enabled)

  // 获取系统状态
  useEffect(() => {
    const fetchSystemStatus = async () => {
      try {
        const data = await systemAPI.getSystemStatus()
        setSystemStatus(data)
      } catch (error) {
        console.error('获取系统状态失败:', error)
      }
    }

    fetchSystemStatus()
  }, [])

  useEffect(() => {
    if (!transcriptionEnabled) {
      setRecentSummaries([])
      return
    }

    const fetchRecentSummaries = async () => {
      try {
        const data = await summaryAPI.getSummaries()
        setRecentSummaries((data.items || []).slice(0, 3))
      } catch (error) {
        console.error('获取最近文字稿失败:', error)
      }
    }

    fetchRecentSummaries()
  }, [transcriptionEnabled])

  // 计算存储使用百分比
  const storageUsage = systemStatus ? {
    video: Math.round((systemStatus.storage.video_size / 1024 / 1024 / 1024) * 100) / 100,
    summary: Math.round((systemStatus.storage.summary_size / 1024 / 1024) * 100) / 100,
    total: Math.round((systemStatus.storage.total_size / 1024 / 1024 / 1024) * 100) / 100,
    percentage: systemStatus.storage.total_size > 0 ? 
      Math.round((systemStatus.storage.total_size / (2 * 1024 * 1024 * 1024)) * 100) : 0
  } : null

  return (
    <div className="home-page">
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card title="系统概览" bordered={false}>
            <Row gutter={[16, 16]}>
              <Col xs={24} sm={12} md={8}>
                <Statistic
                  title="主播数量"
                  value={systemStatus?.database.anchor_count || 0}
                  prefix={<UserOutlined />}
                  suffix="个"
                />
              </Col>
              <Col xs={24} sm={12} md={8}>
                <Statistic
                  title="录制记录"
                  value={systemStatus?.database.recording_count || 0}
                  prefix={<VideoCameraOutlined />}
                  suffix="条"
                />
              </Col>
              <Col xs={24} sm={12} md={8}>
                <Statistic
                  title={transcriptionEnabled ? '文字稿数量' : '当前模式'}
                  value={transcriptionEnabled ? (systemStatus?.database.summary_count || 0) : '纯录制'}
                  prefix={<FileTextOutlined />}
                  suffix={transcriptionEnabled ? '条' : ''}
                />
              </Col>
            </Row>
          </Card>
        </Col>

        <Col xs={24} md={12}>
          <Card title="存储使用情况" bordered={false}>
            {storageUsage ? (
              <div>
                <div className="storage-item">
                  <div className="storage-label">
                    <span>视频文件</span>
                    <span>{storageUsage.video} GB</span>
                  </div>
                  <Progress percent={storageUsage.percentage} size="small" />
                </div>
                <div className="storage-item">
                  <div className="storage-label">
                    <span>{transcriptionEnabled ? '文字稿文件' : '文字稿文件（历史）'}</span>
                    <span>{storageUsage.summary} MB</span>
                  </div>
                  <Progress percent={storageUsage.percentage} size="small" />
                </div>
                <div className="storage-item">
                  <div className="storage-label">
                    <span>总使用</span>
                    <span>{storageUsage.total} GB / 2 GB</span>
                  </div>
                  <Progress percent={storageUsage.percentage} status={storageUsage.percentage > 80 ? 'warning' : 'normal'} />
                </div>
              </div>
            ) : (
              <div>加载中...</div>
            )}
          </Card>
        </Col>

        <Col xs={24} md={12}>
          <Card title="最近文字稿" bordered={false}>
            {transcriptionEnabled ? (
              <List
                dataSource={recentSummaries}
                renderItem={(item) => (
                  <List.Item>
                    <List.Item.Meta
                      title={
                        <div className="summary-title">
                          <span>{item.recording?.anchor?.name || '-'}</span>
                          <span className="summary-date">{item.recording?.start_time ? new Date(item.recording.start_time).toLocaleDateString() : '-'}</span>
                        </div>
                      }
                      description={item.content_preview || item.content || '暂无文字稿'}
                    />
                    <Tag color="blue">{item.status || 'completed'}</Tag>
                  </List.Item>
                )}
                locale={{ emptyText: '暂无文字稿数据' }}
              />
            ) : (
              <Alert
                type="success"
                showIcon
                message="当前为纯录制模式"
                description="新录制任务完成后会直接保留音视频文件，不再触发文字转写、摘要生成和通知发送。"
              />
            )}
          </Card>
        </Col>

        <Col xs={24}>
          <Card title="系统状态" bordered={false}>
            <div className="status-list">
              <div className="status-item">
                <CheckCircleOutlined className="status-icon success" />
                <span>服务运行正常</span>
              </div>
              <div className="status-item">
                <ClockCircleOutlined className="status-icon info" />
                <span>上次检查: {systemStatus?.timestamp || '未知'}</span>
              </div>
              <div className="status-item">
                <AlertOutlined className="status-icon warning" />
                <span>存储空间使用率: {storageUsage?.percentage || 0}%</span>
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default HomePage
