import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'

import App from './App.jsx'
import AnchorManagement from './pages/AnchorManagement.jsx'
import HomePage from './pages/HomePage.jsx'
import RecordingList from './pages/RecordingList.jsx'
import SummaryDetailPage from './pages/SummaryDetailPage.jsx'
import SummaryList from './pages/SummaryList.jsx'
import SystemSettings from './pages/SystemSettings.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<App />}>
            <Route index element={<HomePage />} />
            <Route path="anchors" element={<AnchorManagement />} />
            <Route path="recordings" element={<RecordingList />} />
            <Route path="summaries" element={<SummaryList />} />
            <Route path="summaries/:summaryId" element={<SummaryDetailPage />} />
            <Route path="settings" element={<SystemSettings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  </React.StrictMode>
)
