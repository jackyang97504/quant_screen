import { useState, useEffect } from 'react'
import {
  Table, Card, message, Select, Space, Badge
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  fetchHistory, fetchAvailableDates
} from '../api'

interface StockItem {
  ts_code: string
  name: string
  industry: string
  score: number
  proba: number
  top_factor: string
  status: string
}

export default function History() {
  const [data, setData] = useState<StockItem[]>([])
  const [dates, setDates] = useState<string[]>([])
  const [selectedDate, setSelectedDate] = useState<string>('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchAvailableDates(60).then(r => {
      setDates(r.dates || [])
      if (r.dates?.length > 0) {
        setSelectedDate(r.dates[0])
      }
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (selectedDate) {
      loadData(selectedDate)
    }
  }, [selectedDate])

  const loadData = async (date: string) => {
    setLoading(true)
    try {
      const res = await fetchHistory(date)
      setData(res.items || [])
    } catch (e) {
      message.error('加载失败')
    } finally {
      setLoading(false)
    }
  }

  const columns: ColumnsType<StockItem> = [
    {
      title: '代码',
      dataIndex: 'ts_code',
      key: 'ts_code',
      width: 100,
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 90,
    },
    {
      title: '行业',
      dataIndex: 'industry',
      key: 'industry',
      width: 100,
      ellipsis: true,
    },
    {
      title: '评分',
      dataIndex: 'score',
      key: 'score',
      width: 80,
      render: (v: number) => v?.toFixed(4) ?? '-',
    },
    {
      title: '上涨概率',
      dataIndex: 'proba',
      key: 'proba',
      width: 90,
      render: (v: number) => {
        const pct = (v * 100).toFixed(1)
        const color = v >= 0.6 ? '#52c41a' : v >= 0.55 ? '#faad14' : '#999'
        return <span style={{ color }}>{pct}%</span>
      },
    },
    {
      title: '主要因子',
      dataIndex: 'top_factor',
      key: 'top_factor',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (v: string) => {
        const map: Record<string, { color: string; text: string }> = {
          pending: { color: 'warning', text: '待确认' },
          confirmed: { color: 'success', text: '已确认' },
          rejected: { color: 'error', text: '已拒绝' },
        }
        const s = map[v] || { color: 'default', text: v }
        return <Badge status={s.color as any} text={s.text} />
      },
    },
  ]

  return (
    <div>
      <Card
        title="历史筛选记录"
        extra={
          <Space>
            <Select
              value={selectedDate}
              onChange={(v) => setSelectedDate(v)}
              style={{ width: 200 }}
              options={dates.map(d => ({ value: d, label: d }))}
              placeholder="选择日期"
            />
          </Space>
        }
        bodyStyle={{ padding: 0 }}
      >
        <Table
          className="stock-table"
          columns={columns}
          dataSource={data}
          rowKey="ts_code"
          loading={loading}
          scroll={{ x: 900 }}
          pagination={{
            pageSize: 50,
            showSizeChanger: false,
            showTotal: (total) => `共 ${total} 只`,
          }}
        />
      </Card>
    </div>
  )
}
