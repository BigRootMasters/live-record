import React from 'react'
import { Alert, Card, List, Tag } from 'antd'

const configItems = [
  { key: '主播配置', value: 'backend/config/anchors.json' },
  { key: '转写 Provider', value: 'backend/.env -> TRANSCRIPTION_PROVIDER' },
  { key: '微信通知', value: 'backend/.env -> WECHAT_WEBHOOK_URL' },
  { key: '直播解析测试', value: 'POST /api/live/resolve' },
  { key: '手动转写测试', value: 'POST /api/recordings/:id/transcribe' }
]

const SystemSettings = () => {
  return (
    <div className="system-settings">
      <div className="page-header">
        <h1>测试说明</h1>
      </div>
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
        message="当前版本以本地配置和接口联调为主"
        description="系统设置页不再维护假表单，避免干扰明天的直播测试。关键配置请直接修改 backend/.env 和 backend/config/anchors.json。"
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
