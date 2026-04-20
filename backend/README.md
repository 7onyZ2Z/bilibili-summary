# Backend

本目录包含原项目后端能力，保留两种调用方式：

- CLI
- FastAPI HTTP 服务

## 环境准备

```bash
python -m pip install -r requirements.txt
cp .env.example .env
```

编辑 .env，配置 OPENAI_API_KEY 与模型参数。

## CLI

```bash
python -m src.main single "https://www.bilibili.com/video/BV1xx411c7mD"
```

## API

```bash
uvicorn src.api:app --host 0.0.0.0 --port 8000
```

接口：

- GET /health
- POST /summaries/single
- POST /summaries/batch
- POST /jobs/single
- POST /jobs/batch
- GET /jobs/{job_id}
- GET /jobs/{job_id}/stream
- GET /jobs/{job_id}/markdown
- GET /jobs/{job_id}/download/md
- GET /jobs/{job_id}/download/pdf

说明：

- 推荐前端使用 `/jobs/*` 任务接口，日志通过 SSE 流式返回。
- 任务结束后可直接请求 markdown 预览与下载接口。
