# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fullstack application for summarizing Bilibili videos into structured markdown notes. Given a video URL, it downloads the audio, transcribes it using Whisper, generates an LLM-based summary with interview-focused Q&A, and renders the output as Markdown (with optional PDF export).

**Architecture:** Python backend (FastAPI + CLI) + Vite frontend

## Development Commands

### Backend

```bash
cd backend

# Install dependencies (adjust python path for your environment)
python -m pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env and set OPENAI_API_KEY

# CLI: Process single video
python -m src.main single "https://www.bilibili.com/video/BV..."

# CLI: Batch process from file (one URL per line, # for comments)
python -m src.main batch --input examples/urls.txt

# HTTP API server
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure API base URL (optional, defaults to http://127.0.0.1:8000)
echo "VITE_API_BASE_URL=http://127.0.0.1:8000" > .env

# Dev server
npm run dev

# Production build
npm run build

# Preview production build
npm run preview
```

## High-Level Architecture

### Backend Pipeline ([src/pipeline/](backend/src/pipeline/))

The `SummaryPipeline` class in [orchestrator.py](backend/src/pipeline/orchestrator.py) orchestrates a 5-step process:

1. **Metadata Extraction** ([parser.py](backend/src/pipeline/parser.py)): Fetches video title, description, and source URL from Bilibili page
2. **Audio Download** ([downloader.py](backend/src/pipeline/downloader.py)): Uses yt-dlp with optional aria2c for concurrent fragment downloads
3. **Transcription** ([transcriber.py](backend/src/pipeline/transcriber.py)): OpenAI Whisper API with automatic audio segmentation for large files
4. **Summarization** ([summarizer.py](backend/src/pipeline/summarizer.py)): LLM chat completion for interview-focused summary and Q&A
5. **Rendering** ([renderer.py](backend/src/pipeline/renderer.py)): Jinja2 template to Markdown output

### API Layer ([src/api.py](backend/src/api.py))

FastAPI with job-based async processing using background threads:

**Job-based endpoints (recommended for frontend):**
- `/jobs/single` - Create single-video job
- `/jobs/batch` - Create batch processing job
- `/jobs/{job_id}` - Get job status
- `/jobs/{job_id}/stream` - SSE stream for real-time logs
- `/jobs/{job_id}/cancel` - Cancel a running job
- `/jobs/{job_id}/markdown` - Get markdown content
- `/jobs/{job_id}/download/md` - Download markdown file
- `/jobs/{job_id}/download/pdf` - Export as PDF (Chinese font support via STSong-Light)

**Legacy synchronous endpoints:**
- `/summaries/single` - Process single video (blocking)
- `/summaries/batch` - Process batch (blocking)

### Configuration ([src/config.py](backend/src/config.py))

All settings loaded from `.env` file via python-dotenv. Key settings:
- `OPENAI_API_KEY` - Required API key
- `LLM_BASE_URL` / `LLM_CHAT_PATH` / `LLM_TRANSCRIBE_PATH` - API endpoints
- `SUMMARY_MODEL` / `TRANSCRIBE_MODEL` - Model selection
- `MAX_WORKERS` - Concurrent batch processing
- `DOWNLOAD_USE_ARIA2C` - Enable aria2c for faster downloads

### Data Models ([src/models.py](backend/src/models.py))

Core immutable data structures:
- `VideoMetadata` - Video info (id, title, owner, publish_time, source_url)
- `InterviewQA` - Question-answer pairs for interview prep
- `SummaryResult` - Structured summary with topic, key_points, interview_qas
- `TaskResult` - Per-task outcome (url, success, output_file, error_message)
- `BatchRunReport` - Batch results with success/failure counts

### Frontend ([frontend/src/main.js](frontend/src/main.js))

Vanilla JavaScript (no framework) with Vite:
- SSE-based real-time progress streaming
- Tab-based UI for single/batch modes
- Markdown preview using `marked` library
- API base URL configurable via `VITE_API_BASE_URL`

### Templates ([backend/templates/](backend/templates/))

Jinja2 templates for markdown output. The main template is [summary.md.j2](backend/templates/summary.md.j2).

### Prompts ([src/pipeline/prompts.py](backend/src/pipeline/prompts.py))

Contains `SUMMARY_GUIDELINES` - the system prompt that instructs the LLM to focus on interview-oriented content and realistic Q&A for exam preparation.

### Concurrency Model

- Batch processing: ThreadPoolExecutor via [queue.py](backend/src/pipeline/queue.py) with configurable `MAX_WORKERS`
- Job cancellation: Cooperative cancellation via `cancel_checker` callback
- SSE streaming: Queue-based event delivery per job
