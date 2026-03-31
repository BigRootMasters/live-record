import React from 'react'
import { Alert, Card, List, Tag } from 'antd'

const configItems = [
  { key: '主播配置', value: 'backend/config/anchors.json' },
  { key: '纯录制开关', value: 'backend/.env -> ENABLE_TRANSCRIPTION=False' },
  { key: '监控间隔', value: 'backend/.env -> CHECK_INTERVAL=120' },
  { key: '直播解析测试', value: 'POST /api/live/resolve' },
  { key: '手动停止录制', value: 'POST /api/recordings/:id/stop' }
]

const SystemSettings = () => {
  return (
    <div className="system-settings">
      <div className="page-header">
        <h1>测试说明</h1>
      </div>
      <Alert
        type="success"
        showIcon
        style={{ marginBottom: 16 }}
        message="当前版本已切换为纯录制模式"
        description="新录制完成后只保留音视频文件，不再自动转写、生成文字稿或发送摘要通知。关键配置请直接修改 backend/.env 和 backend/config/anchors.json。"
      />
      <Card title="当前测试入口" bordered={false}>
        <List
          dataSource={configItems}
          renderItem={(item) => (
            <List.Item>
              <List.Item.Meta title={item.key} description={<Tag>{item.value}</Tag>} />
            </List.Item>
          )}
        />
      </Card>
    </div>
  )
}

export default SystemSettings
