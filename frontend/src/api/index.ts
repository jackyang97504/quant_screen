import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 筛选相关
export const fetchTodayScreen = (tradeDate: string) =>
  api.get(`/screen/today?trade_date=${tradeDate}`).then(r => r.data)

export const fetchHistoryScreen = (tradeDate: string) =>
  api.get(`/screen/history?trade_date=${tradeDate}`).then(r => r.data)

export const triggerScreen = (tradeDate?: string) =>
  api.post('/screen/run', { trade_date: tradeDate }).then(r => r.data)

// 股票池
export const fetchPool = (status = 'active') =>
  api.get(`/pool?status=${status}`).then(r => r.data)

export const fetchPending = () =>
  api.get('/pool/pending').then(r => r.data)

export const fetchPoolStats = () =>
  api.get('/pool/stats').then(r => r.data)

export const confirmStocks = (codes: string[]) =>
  api.post('/pool/confirm', { codes }).then(r => r.data)

export const rejectStocks = (codes: string[]) =>
  api.post('/pool/reject', { codes }).then(r => r.data)

export const removeStocks = (codes: string[]) =>
  api.post('/pool/remove', { codes }).then(r => r.data)

// 历史
export const fetchHistory = (tradeDate: string) =>
  api.get(`/history?trade_date=${tradeDate}`).then(r => r.data)

export const fetchAvailableDates = (limit = 30) =>
  api.get(`/history/dates?limit=${limit}`).then(r => r.data)

// 健康检查
export const fetchHealth = () =>
  api.get('/health').then(r => r.data)
