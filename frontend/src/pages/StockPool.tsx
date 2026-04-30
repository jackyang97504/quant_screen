import { useState, useEffect } from 'react'
import {
  Table, Card, Tag, Button, Statistic, Row, Col,
  message, Popconfirm, Badge
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  DeleteOutlined, ReloadOutlined,
  CheckCircleOutlined, ClockCircleOutlined, WarningOutlined
} from '@ant-design/icons'
import {
  fetchPool, fetchPoolStats, removeStocks
} from '../api'

interface PoolItem {
  ts_code: string
  name: string
  industry: string
  first_seen: string
  last_seen: string
  hit_count: number
  days_in_pool: number
  status: string
}

export default function StockPool() {
  const [data, setData] = useState<PoolItem[]>([])
  const [stats, setStats] = useState<any>({})
  const [loading, setLoading] = useState(false)
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([])

  const loadData = async () => {
    setLoading(true)
    try {
      const [poolRes, statsRes] = await Promise.all([
        fetchPool('active'),
        fetchPoolStats(),
      ])
      setData(poolRes.items || [])
      setStats(statsRes)
    } catch (e) {
      message.error('加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleRemove = async (codes: string[]) => {
    try {
      const res = await removeStocks(codes)
      message.success(res.message)
      setSelectedRowKeys([])
      loadData()
    } catch (e) {
      message.error('移除失败')
    }
  }

  const columns: ColumnsType<PoolItem> = [
    {
      title: '代码',
      dataIndex: 'ts_code',
      key: 'ts_code',
      width: 110,
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
      title: '入池日期',
      dataIndex: 'first_seen',
      key: 'first_seen',
      width: 100,
      render: (v: string) => v?.split('T')[0] ?? '-',
    },
    {
      title: '最近入选',
      dataIndex: 'last_seen',
      key: 'last_seen',
      width: 100,
      render: (v: string) => v?.split('T')[0] ?? '-',
    },
    {
      title: '命中次数',
      dataIndex: 'hit_count',
      key: 'hit_count',
      width: 90,
      sorter: (a, b) => a.hit_count - b.hit_count,
      render: (v: number) => (
        <Tag color={v >= 5 ? 'green' : v >= 2 ? 'blue' : 'default'}>
          {v} 次
        </Tag>
      ),
    },
    {
      title: '在池天数',
      dataIndex: 'days_in_pool',
      key: 'days_in_pool',
      width: 90,
      sorter: (a, b) => a.days_in_pool - b.days_in_pool,
      render: (v: number) => {
        if (v >= 15) return <Tag color="red">{v} 天</Tag>
        if (v >= 10) return <Tag color="warning">{v} 天</Tag>
        return <Tag>{v} 天</Tag>
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (v: string) => {
        const map: Record<string, { color: string; text: string }> = {
          active: { color: 'success', text: '活跃' },
          expired: { color: 'error', text: '已过期' },
          removed: { color: 'default', text: '已移出' },
        }
        const s = map[v] || { color: 'default', text: v }
        return <Badge status={s.color as any} text={s.text} />
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      fixed: 'right',
      render: (_, record) => (
        <Popconfirm
          title="确定移出该股票？"
          onConfirm={() => handleRemove([record.ts_code])}
          okText="确定"
          cancelText="取消"
        >
          <Button size="small" danger icon={<DeleteOutlined />}>
            移出
          </Button>
        </Popconfirm>
      ),
    },
  ]

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="当前池内"
              value={stats.active_count ?? data.length}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="平均命中"
              value={stats.avg_hit_count?.toFixed(1) ?? '-'}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="最高命中"
              value={stats.max_hit_count ?? '-'}
              prefix={<WarningOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title="股票池"
        extra={
          <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading}>
            刷新
          </Button>
        }
        bodyStyle={{ padding: 0 }}
      >
        <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0', background: '#fafafa' }}>
          <Popconfirm
            title={`确定移出选中的 ${selectedRowKeys.length} 只股票？`}
            onConfirm={() => handleRemove(selectedRowKeys)}
            okText="确定"
            cancelText="取消"
            disabled={selectedRowKeys.length === 0}
          >
            <Button
              danger
              icon={<DeleteOutlined />}
              disabled={selectedRowKeys.length === 0}
            >
              批量移出 ({selectedRowKeys.length})
            </Button>
          </Popconfirm>
        </div>

        <Table
          className="stock-table"
          columns={columns}
          dataSource={data}
          rowKey="ts_code"
          loading={loading}
          rowSelection={{
            selectedRowKeys,
            onChange: (keys) => setSelectedRowKeys(keys as string[]),
          }}
          scroll={{ x: 900 }}
          pagination={{
            pageSize: 50,
            showSizeChanger: false,
            showTotal: (total) => `共 ${total} 只`,
          }}
          rowClassName={(record) =>
            record.days_in_pool >= 15 ? 'pool-expired' : ''
          }
        />
      </Card>
    </div>
  )
}
