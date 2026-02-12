import React, { useEffect, useState } from 'react'
import { Card, Row, Col, Statistic, Progress, List, Button, Space } from 'antd'
import { UserOutlined, VideoCameraOutlined, FileTextOutlined, CheckCircleOutlined, ClockCircleOutlined, AlertOutlined } from '@ant-design/icons'
import axios from 'axios'

function HomePage() {
  const [systemStatus, setSystemStatus] = useState(null)
  const [recentSummaries, setRecentSummaries] = useState([])
  const [loading, setLoading] = useState(true)

  // 获取系统状态
  useEffect(() => {
    const fetchSystemStatus = async () => {
      try {
        const response = await axios.get('/api/system/status')
        setSystemStatus(response.data)
      } catch (error) {
        console.error('获取系统状态失败:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchSystemStatus()
  }, [])

  // 模拟最近摘要数据
  useEffect(() => {
    setRecentSummaries([
      {
        id: 1,
        anchorName: '财经主播张三',
        date: '2026-02-12',
        content: '今天分析了当前股市走势，认为新能源板块还有上涨空间...',
        status: 'completed'
      },
      {
        id: 2,
        anchorName: '财经主播李四',
        date: '2026-02-11',
        content: '讨论了半导体行业的发展前景，建议关注龙头企业...',
        status: 'completed'
      },
      {
        id: 3,
        anchorName: '财经主播王五',
        date: '2026-02-10',
        content: '解读了最新的经济数据，认为经济复苏势头良好...',
        status: 'completed'
      }
    ])
  }, [])

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
                  title="内容摘要"
                  value={systemStatus?.database.summary_count || 0}
                  prefix={<FileTextOutlined />}
                  suffix="条"
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
                    <span>摘要文件</span>
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
          <Card title="最近摘要" bordered={false}>
            <List
              dataSource={recentSummaries}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <Button size="small" type="primary">查看详情</Button>
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <div className="summary-title">
                        <span>{item.anchorName}</span>
                        <span className="summary-date">{item.date}</span>
                      </div>
                    }
                    description={item.content}
                  />
                </List.Item>
              )}
              locale={{ emptyText: '暂无摘要数据' }}
            />
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