import React from 'react'
import { Layout, Menu, Button, Badge } from 'antd'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { HomeOutlined, UserOutlined, VideoCameraOutlined, FileTextOutlined, SettingOutlined, PlusOutlined } from '@ant-design/icons'
import './App.css'
import HomePage from './pages/HomePage'
import AnchorManagement from './pages/AnchorManagement'
import RecordingList from './pages/RecordingList'
import SummaryList from './pages/SummaryList'
import SystemSettings from './pages/SystemSettings'

const { Header, Content, Sider } = Layout

function App() {
  const location = useLocation()
  const currentPath = location.pathname

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
      key: '/summaries',
      icon: <FileTextOutlined />,
      label: <Link to="/summaries">内容摘要</Link>
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: <Link to="/settings">系统设置</Link>
    }
  ]

  return (
    <Layout>
      <Header className="header">
        <div className="logo">抖音直播录制系统</div>
        <div className="header-actions">
          <Button type="primary" icon={<PlusOutlined />}>
            添加主播
          </Button>
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