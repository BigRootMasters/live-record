import React, { useEffect, useState } from 'react'
import { Layout, Menu, Tag } from 'antd'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { HomeOutlined, UserOutlined, VideoCameraOutlined, FileTextOutlined, SettingOutlined } from '@ant-design/icons'
import { systemAPI } from './api'
import './App.css'

const { Header, Content, Sider } = Layout

function App() {
  const location = useLocation()
  const currentPath = location.pathname
  const [transcriptionEnabled, setTranscriptionEnabled] = useState(false)

  useEffect(() => {
    const fetchSystemStatus = async () => {
      try {
        const data = await systemAPI.getSystemStatus()
        setTranscriptionEnabled(Boolean(data?.features?.transcription_enabled))
      } catch (error) {
        console.error('获取系统功能配置失败:', error)
      }
    }

    fetchSystemStatus()
  }, [])

  // 菜单项配置
  const menuItems = [
    {
      key: '/',
      icon: <HomeOutlined />,
      label: <Link to="/">首页</Link>
    },
    {
      key: '/anchors',
      icon: <UserOutlined />,
      label: <Link to="/anchors">主播管理</Link>
    },
    {
      key: '/recordings',
      icon: <VideoCameraOutlined />,
      label: <Link to="/recordings">录制记录</Link>
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: <Link to="/settings">系统设置</Link>
    }
  ]

  if (transcriptionEnabled) {
    menuItems.splice(3, 0, {
      key: '/summaries',
      icon: <FileTextOutlined />,
      label: <Link to="/summaries">文字稿</Link>
    })
  }

  return (
    <Layout>
      <Header className="header">
        <div className="logo">抖音直播录制系统</div>
        <div className="header-actions">
          <Tag color={transcriptionEnabled ? 'blue' : 'green'}>
            {transcriptionEnabled ? '录制 + 转写' : '纯录制模式'}
          </Tag>
        </div>
      </Header>
      <Layout>
        <Sider width={200} className="sider">
          <Menu
            mode="inline"
            selectedKeys={[currentPath]}
            items={menuItems}
            className="menu"
          />
        </Sider>
        <Layout className="content-layout">
          <Content className="content">
            <Outlet />
          </Content>
        </Layout>
      </Layout>
    </Layout>
  )
}

export default App
