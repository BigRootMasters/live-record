import axios from 'axios'

// 创建axios实例
const api = axios.create({
  baseURL: 'http://localhost:5000/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 响应拦截器
api.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    console.error('API请求错误:', error)
    return Promise.reject(error)
  }
)

// 主播管理API
export const anchorAPI = {
  // 获取所有主播
  getAnchors: () => api.get('/anchors'),
  
  // 添加新主播
  addAnchor: (data) => api.post('/anchors', data),
  
  // 更新主播信息
  updateAnchor: (id, data) => api.put(`/anchors/${id}`, data),
  
  // 删除主播
  deleteAnchor: (id) => api.delete(`/anchors/${id}`)
}

// 录制记录API
export const recordingAPI = {
  // 获取所有录制记录
  getRecordings: () => api.get('/recordings'),
  
  // 获取单个录制记录详情
  getRecording: (id) => api.get(`/recordings/${id}`)
}

// 摘要API
export const summaryAPI = {
  // 获取所有摘要
  getSummaries: () => api.get('/summaries'),
  
  // 获取单个摘要详情
  getSummary: (id) => api.get(`/summaries/${id}`)
}

// 系统状态API
export const systemAPI = {
  // 获取系统状态
  getSystemStatus: () => api.get('/system/status')
}

export default api