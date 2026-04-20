# Bilibili Summary

将 B 站视频一键转为结构化 Markdown 笔记，聚焦面试知识点与问答。

输入视频链接，自动完成 **音频下载 → Whisper 转写 → LLM 总结 → Markdown 渲染**，输出含面试 Q&A 的结构化笔记，支持导出 PDF。

## 功能特性

- **单视频 / 批量处理** — 支持一次处理多个视频链接
- **实时进度流** — 基于 SSE 的五阶段进度展示
- **智能缓存** — 已处理视频自动缓存，二次请求秒出结果
- **Markdown 预览** — 前端实时渲染总结内容
- **PDF 导出** — 内置中文排版支持的 PDF 生成
- **任务管理** — 异步 Job 模型，支持取消、状态查询

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python · FastAPI · yt-dlp · OpenAI Whisper · Jinja2 |
| 前端 | Vanilla JS · Vite · marked |
| AI   | Whisper (语音转写) · LLM Chat (内容总结) |

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- OPENAI_API_KEY（兼容 OpenAI 接口的 Key）

### 后端

```bash
cd backend
python -m pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填写 OPENAI_API_KEY
```

### 前端

```bash
cd frontend
npm install
```

## 使用方式

### CLI

处理单个视频：

```bash
cd backend
python -m src.main single "https://www.bilibili.com/video/BV1xx411c7mD"
```

批量处理（文件中一行一个链接，`#` 开头为注释）：

```bash
python -m src.main batch --input examples/urls.txt
```

### HTTP API

启动服务：

```bash
cd backend
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

主要接口：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/jobs/single` | 提交单视频任务 |
| POST | `/jobs/batch` | 提交批量任务 |
| GET  | `/jobs/{job_id}` | 查询任务状态 |
| GET  | `/jobs/{job_id}/stream` | SSE 实时日志流 |
| POST | `/jobs/{job_id}/cancel` | 取消任务 |
| GET  | `/jobs/{job_id}/markdown` | 获取 Markdown 内容 |
| GET  | `/jobs/{job_id}/download/md` | 下载 Markdown 文件 |
| GET  | `/jobs/{job_id}/download/pdf` | 导出 PDF |

### 前端

```bash
cd frontend
npm run dev
```

访问 http://127.0.0.1:5173 即可使用。前端默认连接 `http://127.0.0.1:8000`，可通过 `frontend/.env` 修改：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 处理流程

```
视频链接 → 元数据解析 → 音频下载 → Whisper 转写 → LLM 总结 → Markdown 渲染 → 输出
```

1. **元数据解析** — 提取视频标题、描述、UP 主等信息
2. **音频下载** — yt-dlp 下载，可选 aria2c 加速
3. **语音转写** — Whisper API 自动分段处理长音频
4. **内容总结** — LLM 生成面试导向的结构化笔记与 Q&A
5. **渲染输出** — Jinja2 模板生成 Markdown

## 配置项

在 `backend/.env` 中配置，完整列表见 `backend/.env.example`：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_API_KEY` | — | **必填**，API 密钥 |
| `LLM_BASE_URL` | `https://yunwu.ai` | API 基础地址 |
| `SUMMARY_MODEL` | `qwen3-vl-30b-a3b-instruct` | 总结模型 |
| `TRANSCRIBE_MODEL` | `whisper-1` | 转写模型 |
| `MAX_WORKERS` | `2` | 批量并发数 |
| `DOWNLOAD_USE_ARIA2C` | `true` | 启用 aria2c 加速下载 |

## 项目结构

```
├── backend/
│   ├── src/
│   │   ├── api.py              # FastAPI 应用与路由
│   │   ├── config.py           # 配置加载
│   │   ├── main.py             # CLI 入口
│   │   ├── models.py           # 数据模型
│   │   └── pipeline/
│   │       ├── orchestrator.py  # 流程编排
│   │       ├── parser.py        # 元数据解析
│   │       ├── downloader.py    # 音频下载
│   │       ├── transcriber.py   # 语音转写
│   │       ├── summarizer.py    # LLM 总结
│   │       ├── renderer.py      # Markdown 渲染
│   │       ├── cache.py         # 结果缓存
│   │       └── prompts.py       # LLM 提示词
│   ├── templates/              # Jinja2 模板
│   └── examples/               # 示例文件
├── frontend/
│   └── src/
│       ├── main.js             # 前端应用逻辑
│       └── styles.css          # 样式
└── README.md
```

## License

MIT
