# Bilibili Summary Fullstack

当前项目已拆分为前后端分离结构：

- backend: Python 后端（CLI + FastAPI）
- frontend: 前端 demo（Vite）

## 目录结构

```text
backend/
frontend/
```

## 启动后端

```bash
cd backend
python -m pip install -r requirements.txt
cp .env.example .env
```

编辑 backend/.env，填写 OPENAI_API_KEY。

### CLI 调用

```bash
cd backend
python -m src.main single "https://www.bilibili.com/video/BV1xx411c7mD"
```

### HTTP 服务调用

```bash
cd backend
uvicorn src.api:app --host 0.0.0.0 --port 8000
```

接口：

- GET /health
- POST /summaries/single
- POST /summaries/batch

## 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认访问地址：

- <http://127.0.0.1:5173>

默认会请求后端：

- <http://127.0.0.1:8000>

可通过 frontend/.env 覆盖：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```
