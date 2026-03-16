import React from 'react'
import { Alert, Card, List, Tag } from 'antd'

const configItems = [
  { key: '主播配置', value: 'backend/config/anchors.json' },
  { key: '转写 Provider', value: 'backend/.env -> TRANSCRIPTION_PROVIDER' },
  { key: '阿里云 Key', value: 'backend/.env -> ALIYUN_DASHSCOPE_API_KEY' },
  { key: '公网地址', value: 'backend/.env -> PUBLIC_BASE_URL' },
  { key: '微信通知', value: 'backend/.env -> WECHAT_WEBHOOK_URL' },
  { key: '通知链接', value: 'backend/.env -> TRANSCRIPT_BASE_URL' },
  { key: '即时推送', value: 'backend/.env -> AUTO_NOTIFY_ON_TRANSCRIBE=True' },
  { key: '监控间隔', value: 'backend/.env -> CHECK_INTERVAL=120' },
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
        message="当前版本按轻量部署方案配置"
        description="当前已支持本地转写和阿里云 Paraformer。关键配置请直接修改 backend/.env 和 backend/config/anchors.json。"
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
