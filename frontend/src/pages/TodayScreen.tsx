import { useState, useEffect } from 'react'
import {
  Table, Tag, Button, Space, Card, Statistic, Row, Col,
  message, DatePicker, Modal, Tooltip, Badge, Descriptions
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  CheckOutlined, CloseOutlined, ReloadOutlined,
  ThunderboltOutlined, InfoCircleOutlined
} from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  fetchTodayScreen, fetchPending,
  confirmStocks, rejectStocks, triggerScreen,
  fetchAvailableDates
} from '../api'

interface StockItem {
  ts_code: string
  name: string
  industry: string
  score: number
  proba: number
  top_factor: string
  screening_detail?: string
  status: string
  created_at: string
}

interface ScreeningDetail {
  prob: number
  industry: string
  risk_level: string
  positive_signals: string[]
  negative_signals: string[]
  warnings: string[]
  key_indicators: Record<string, string>
  industry_context: Record<string, string>
}

export default function TodayScreen() {
  const [data, setData] = useState<StockItem[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([])
  const [tradeDate, setTradeDate] = useState<string>('')
  const [pendingCount, setPendingCount] = useState(0)
  const [detailItem, setDetailItem] = useState<StockItem | null>(null)

  const loadData = async (date: string) => {
    if (!date) return
    setLoading(true)
    try {
      const [screenRes, pendingRes] = await Promise.all([
        fetchTodayScreen(date),
        fetchPending(),
      ])
      setData(screenRes.items || [])
      setPendingCount(pendingRes.total || 0)
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载失败')
    } finally {
      setLoading(false)
    }
  }

  // 挂载时取最近有数据的日期
  useEffect(() => {
    fetchAvailableDates(1).then(res => {
      if (res.dates && res.dates.length > 0) {
        setTradeDate(res.dates[0])
      } else {
        setTradeDate(dayjs().format('YYYY-MM-DD'))
      }
    }).catch(() => {
      setTradeDate(dayjs().format('YYYY-MM-DD'))
    })
  }, [])

  useEffect(() => {
    if (tradeDate) loadData(tradeDate)
  }, [tradeDate])

  const handleConfirm = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择股票')
      return
    }
    try {
      const res = await confirmStocks(selectedRowKeys)
      message.success(res.message)
      setSelectedRowKeys([])
      loadData(tradeDate)
    } catch (e: any) {
      message.error('确认失败')
    }
  }

  const handleReject = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择股票')
      return
    }
    try {
      const res = await rejectStocks(selectedRowKeys)
      message.success(res.message)
      setSelectedRowKeys([])
      loadData(tradeDate)
    } catch (e: any) {
      message.error('拒绝失败')
    }
  }

  const handleRunScreen = async () => {
    try {
      const res = await triggerScreen()
      message.info(res.message + '，数据可能有延迟，请稍后刷新')
    } catch (e) {
      message.error('触发失败')
    }
  }

  const columns: ColumnsType<StockItem> = [
    {
      title: '代码',
      dataIndex: 'ts_code',
      key: 'ts_code',
      width: 100,
      fixed: 'left',
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
      sorter: (a, b) => a.score - b.score,
      render: (v: number) => v?.toFixed(4) ?? '-',
    },
    {
      title: '上涨概率',
      dataIndex: 'proba',
      key: 'proba',
      width: 90,
      sorter: (a, b) => a.proba - b.proba,
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
      render: (v: string) => (
        <Tooltip title={v}>{v || '-'}</Tooltip>
      ),
    },
    {
      title: '详情',
      key: 'detail',
      width: 70,
      render: (_: any, record: StockItem) => (
        <Button
          size="small"
          icon={<InfoCircleOutlined />}
          onClick={() => setDetailItem(record)}
        >
          详情
        </Button>
      ),
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
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="当日选出"
              value={data.length}
              prefix={<ThunderboltOutlined />}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="待确认"
              value={pendingCount}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title={`筛选结果 — ${tradeDate}`}
        extra={
          <Space>
            <DatePicker
              value={dayjs(tradeDate)}
              onChange={(d) => d && setTradeDate(d.format('YYYY-MM-DD'))}
              allowClear={false}
            />
            <Button
              icon={<ReloadOutlined />}
              onClick={() => loadData(tradeDate)}
              loading={loading}
            >
              刷新
            </Button>
            <Button
              type="dashed"
              icon={<ThunderboltOutlined />}
              onClick={handleRunScreen}
            >
              触发筛选
            </Button>
          </Space>
        }
        bodyStyle={{ padding: 0 }}
      >
        <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0', background: '#fafafa' }}>
          <Space>
            <Button
              type="primary"
              icon={<CheckOutlined />}
              onClick={handleConfirm}
              disabled={selectedRowKeys.length === 0}
            >
              确认入选 ({selectedRowKeys.length})
            </Button>
            <Button
              danger
              icon={<CloseOutlined />}
              onClick={handleReject}
              disabled={selectedRowKeys.length === 0}
            >
              拒绝 ({selectedRowKeys.length})
            </Button>
          </Space>
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
        />
      </Card>

      {/* 详情弹窗 */}
      <Modal
        open={!!detailItem}
        title={`${detailItem?.name} (${detailItem?.ts_code}) — 筛选详情`}
        onCancel={() => setDetailItem(null)}
        footer={
          <Button type="primary" onClick={() => setDetailItem(null)}>
            关闭
          </Button>
        }
        width={600}
      >
        {detailItem?.screening_detail && (() => {
          let detail: ScreeningDetail | null = null
          try {
            detail = JSON.parse(detailItem.screening_detail || '{}')
          } catch { detail = null }
          if (!detail) return <p>详情数据解析失败</p>
          return (
            <div>
              <Space style={{ marginBottom: 16 }}>
                <Tag color={detail.risk_level === '高' ? 'red' : detail.risk_level === '中' ? 'orange' : 'green'}>
                  风险等级: {detail.risk_level}
                </Tag>
                <Tag color="blue">上涨概率: {(detail.prob * 100).toFixed(1)}%</Tag>
                <Tag>行业: {detail.industry}</Tag>
              </Space>

              {detail.positive_signals && detail.positive_signals.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ color: '#52c41a', fontWeight: 600, marginBottom: 6 }}>✓ 正面信号</div>
                  {detail.positive_signals.map((s, i) => (
                    <Tag color="success" key={i} style={{ marginBottom: 4 }}>{s}</Tag>
                  ))}
                </div>
              )}

              {detail.negative_signals && detail.negative_signals.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ color: '#ff4d4f', fontWeight: 600, marginBottom: 6 }}>✗ 负面信号</div>
                  {detail.negative_signals.map((s, i) => (
                    <Tag color="error" key={i} style={{ marginBottom: 4 }}>{s}</Tag>
                  ))}
                </div>
              )}

              {detail.warnings && detail.warnings.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ color: '#faad14', fontWeight: 600, marginBottom: 6 }}>⚠ 风险提示</div>
                  {detail.warnings.map((s, i) => (
                    <Tag color="warning" key={i} style={{ marginBottom: 4 }}>{s}</Tag>
                  ))}
                </div>
              )}

              <Descriptions bordered size="small" column={2} title="关键指标" style={{ marginTop: 16 }}>
                {Object.entries(detail.key_indicators || {}).map(([k, v]) => (
                  <Descriptions.Item key={k} label={k}>{v}</Descriptions.Item>
                ))}
              </Descriptions>

              <Descriptions bordered size="small" column={2} title="行业背景" style={{ marginTop: 12 }}>
                {Object.entries(detail.industry_context || {}).map(([k, v]) => (
                  <Descriptions.Item key={k} label={k}>{v}</Descriptions.Item>
                ))}
              </Descriptions>
            </div>
          )
        })()}
      </Modal>
    </div>
  )
}
