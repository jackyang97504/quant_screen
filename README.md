# 量化选股系统

每日量化选股生产系统，FastAPI 后端 + React 前端。

## 项目结构

```
quant_screen/
├── backend/               # FastAPI 后端
│   ├── main.py           # 入口
│   ├── config.py         # 配置管理
│   ├── database.py       # PostgreSQL 连接
│   ├── routers/          # API 路由
│   ├── services/         # 核心服务
│   └── requirements.txt
├── frontend/             # React 前端
│   ├── src/pages/        # 页面组件
│   └── package.json
└── models/              # 模型文件
```

## 快速启动

### 1. 后端

```bash
cd backend
pip install -r requirements.txt

# 配置 .env（设置 tushare_token 和 database_url）
cp .env.example .env

# 启动
uvicorn main:app --reload --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

### 3. 定时任务

定时任务在 FastAPI 启动时自动启动：
- **盘中**：每天 09:35
- **盘后**：每天 15:35

## 配置

在 `backend/.env` 中设置：

```env
TUSHARE_TOKEN=your_token_here
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quant_screen
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `GET /api/screen/today?trade_date=YYYY-MM-DD` | GET | 当日筛选结果 |
| `GET /api/pool` | GET | 当前股票池 |
| `GET /api/pool/pending` | GET | 待确认列表 |
| `POST /api/pool/confirm` | POST | 确认入选 |
| `POST /api/pool/reject` | POST | 拒绝入选 |
| `POST /api/screen/run` | POST | 手动触发筛选 |
| `GET /api/history?trade_date=YYYY-MM-DD` | GET | 历史查询 |
