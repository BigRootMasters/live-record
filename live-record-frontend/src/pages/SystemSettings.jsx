import React, { useState } from 'react'
import { Form, Button, Input, Switch, Select, Card, message, Tabs, Upload, Space, Progress } from 'antd'
import { SaveOutlined, UploadOutlined, DeleteOutlined } from '@ant-design/icons'

const { TabPane } = Tabs
const { Option } = Select

const SystemSettings = () => {
  const [form] = Form.useForm()
  const [storageUsage, setStorageUsage] = useState(65)
  const [logs, setLogs] = useState([
    {
      id: 1,
      time: '2024-01-01 21:30:00',
      level: 'info',
      message: '主播A直播录制完成，时长1小时30分钟'
    },
    {
      id: 2,
      time: '2024-01-01 21:40:00',
      level: 'info',
      message: '内容摘要生成完成，共850字'
    },
    {
      id: 3,
      time: '2024-01-01 21:45:00',
      level: 'info',
      message: '摘要已发送到邮箱: user@example.com'
    },
    {
      id: 4,
      time: '2024-01-02 20:00:00',
      level: 'info',
      message: '检测到主播A正在直播，开始录制'
    }
  ])

  const handleSave = (values) => {
    console.log('保存设置:', values)
    message.success('设置保存成功')
  }

  const handleClearLogs = () => {
    setLogs([])
    message.success('日志已清空')
  }

  const handleClearStorage = () => {
    setStorageUsage(10)
    message.success('存储已清理')
  }

  return (
    <div className="system-settings">
      <div className="page-header">
        <h1>系统设置</h1>
      </div>
      <Tabs defaultActiveKey="1">
        <TabPane tab="基本设置" key="1">
          <Card title="系统配置">
            <Form
              form={form}
              layout="vertical"
              onFinish={handleSave}
              initialValues={{
                checkInterval: 5,
                recordingQuality: '720p',
                enableNotification: true,
                notificationMethod: 'email',
                email: 'user@example.com',
                wechatToken: '',
                openaiApiKey: 'sk-********************************',
                summaryLength: 500,
                enableAutoDelete: true,
                deleteAfterDays: 7
              }}
            >
              <Form.Item
                name="checkInterval"
                label="直播检测间隔（分钟）"
                rules={[{ required: true, message: '请输入检测间隔' }]}
              >
                <Input type="number" min={1} max={60} />
              </Form.Item>
              <Form.Item
                name="recordingQuality"
                label="录制质量"
                rules={[{ required: true, message: '请选择录制质量' }]}
              >
                <Select>
                  <Option value="480p">480p</Option>
                  <Option value="720p">720p</Option>
                  <Option value="1080p">1080p</Option>
                </Select>
              </Form.Item>
              <Form.Item
                name="summaryLength"
                label="摘要长度（字）"
                rules={[{ required: true, message: '请输入摘要长度' }]}
              >
                <Input type="number" min={100} max={2000} />
              </Form.Item>
              <Form.Item
                name="enableAutoDelete"
                label="启用自动删除"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
              <Form.Item
                name="deleteAfterDays"
                label="自动删除天数"
                rules={[{ required: true, message: '请输入自动删除天数' }]}
              >
                <Input type="number" min={1} max={30} />
              </Form.Item>
              <Form.Item>
                <Button type="primary" icon={<SaveOutlined />} htmlType="submit">
                  保存设置
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </TabPane>
        <TabPane tab="通知设置" key="2">
          <Card title="通知配置">
            <Form
              form={form}
              layout="vertical"
              onFinish={handleSave}
            >
              <Form.Item
                name="enableNotification"
                label="启用通知"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
              <Form.Item
                name="notificationMethod"
                label="通知方式"
                rules={[{ required: true, message: '请选择通知方式' }]}
              >
                <Select>
                  <Option value="email">邮件</Option>
                  <Option value="wechat">微信</Option>
                  <Option value="both">邮件和微信</Option>
                </Select>
              </Form.Item>
              <Form.Item
                name="email"
                label="邮箱地址"
                rules={[{ required: true, message: '请输入邮箱地址' }]}
              >
                <Input placeholder="请输入邮箱地址" />
              </Form.Item>
              <Form.Item
                name="wechatToken"
                label="微信机器人Token"
              >
                <Input placeholder="请输入微信机器人Token" />
              </Form.Item>
              <Form.Item>
                <Button type="primary" icon={<SaveOutlined />} htmlType="submit">
                  保存设置
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </TabPane>
        <TabPane tab="API配置" key="3">
          <Card title="API配置">
            <Form
              form={form}
              layout="vertical"
              onFinish={handleSave}
            >
              <Form.Item
                name="openaiApiKey"
                label="OpenAI API Key"
                rules={[{ required: true, message: '请输入API Key' }]}
              >
                <Input.Password placeholder="请输入OpenAI API Key" />
              </Form.Item>
              <Form.Item>
                <Button type="primary" icon={<SaveOutlined />} htmlType="submit">
                  保存设置
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </TabPane>
        <TabPane tab="存储管理" key="4">
          <Card title="存储使用情况">
            <div style={{ marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span>总存储: 50GB</span>
                <span>已使用: {storageUsage}GB ({storageUsage * 2}%)</span>
              </div>
              <Progress percent={storageUsage * 2} status="active" />
            </div>
            <div style={{ display: 'flex', gap: 16 }}>
              <Button danger icon={<DeleteOutlined />} onClick={handleClearStorage}>
                清理存储
              </Button>
              <Button>
                查看存储详情
              </Button>
            </div>
          </Card>
        </TabPane>
        <TabPane tab="系统日志" key="5">
          <Card title="系统日志">
            <div style={{ marginBottom: 16 }}>
              <Button danger icon={<DeleteOutlined />} onClick={handleClearLogs}>
                清空日志
              </Button>
            </div>
            <div style={{ maxHeight: 400, overflowY: 'auto', border: '1px solid #f0f0f0', padding: 16 }}>
              {logs.map((log, index) => (
                <div key={index} style={{ marginBottom: 8, paddingBottom: 8, borderBottom: '1px solid #f0f0f0' }}>
                  <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>{log.time}</div>
                  <div style={{ fontSize: 14 }}>
                    <span style={{ marginRight: 12, color: log.level === 'error' ? 'red' : log.level === 'warn' ? 'orange' : 'green' }}>
                      [{log.level.toUpperCase()}]
                    </span>
                    {log.message}
                  </div>
                </div>
              ))}
              {logs.length === 0 && (
                <div style={{ textAlign: 'center', color: '#999', padding: 40 }}>
                  暂无日志记录
                </div>
              )}
            </div>
          </Card>
        </TabPane>
        <TabPane tab="关于系统" key="6">
          <Card title="关于系统">
            <div style={{ lineHeight: 2 }}>
              <p><strong>系统名称:</strong> 抖音财经直播监测系统</p>
              <p><strong>版本:</strong> 1.0.0</p>
              <p><strong>描述:</strong> 自动监测并录制抖音财经主播的直播，提取核心观点和内容，通过邮件或微信推送摘要</p>
              <p><strong>技术栈:</strong></p>
              <ul style={{ marginLeft: 20 }}>
                <li>后端: Python, Flask, SQLite</li>
                <li>前端: React, Ant Design</li>
                <li>视频处理: FFmpeg</li>
                <li>内容分析: OpenAI API</li>
              </ul>
              <p><strong>最后更新:</strong> 2024-01-01</p>
            </div>
          </Card>
        </TabPane>
      </Tabs>
    </div>
  )
}

export default SystemSettings