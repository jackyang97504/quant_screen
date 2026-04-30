import { useState, lazy, Suspense } from 'react'
import { Layout, Menu, Typography, ConfigProvider, Spin } from 'antd'
import { FundProjectionScreenOutlined, AppstoreOutlined, HistoryOutlined } from '@ant-design/icons'

const TodayScreen = lazy(() => import('./pages/TodayScreen'))
const StockPool = lazy(() => import('./pages/StockPool'))
const History = lazy(() => import('./pages/History'))

const { Header, Content } = Layout
const { Title } = Typography

type PageKey = 'today' | 'pool' | 'history'

function App() {
  const [activePage, setActivePage] = useState<PageKey>('today')

  const renderPage = () => {
    switch (activePage) {
      case 'today': return <TodayScreen />
      case 'pool':  return <StockPool />
      case 'history': return <History />
    }
  }

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#1890ff',
        },
      }}
    >
      <Layout style={{ minHeight: '100vh' }}>
        <Header style={{
          display: 'flex', alignItems: 'center',
          borderBottom: '1px solid #f0f0f0',
          background: '#fff',
        }}>
          <div style={{ marginRight: 40 }}>
            <Title level={4} style={{ margin: 0, color: '#1890ff' }}>
              量化选股系统
            </Title>
          </div>
          <Menu
            mode="horizontal"
            selectedKeys={[activePage]}
            onClick={({ key }) => setActivePage(key as PageKey)}
            items={[
              {
                key: 'today',
                icon: <FundProjectionScreenOutlined />,
                label: '当日筛选',
              },
              {
                key: 'pool',
                icon: <AppstoreOutlined />,
                label: '股票池',
              },
              {
                key: 'history',
                icon: <HistoryOutlined />,
                label: '历史查询',
              },
            ]}
            style={{ border: 'none', flex: 1 }}
          />
        </Header>
        <Content style={{ padding: '24px' }}>
          <Suspense fallback={<Spin />}>
            {renderPage()}
          </Suspense>
        </Content>
      </Layout>
    </ConfigProvider>
  )
}

export default App
