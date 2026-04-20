from __future__ import annotations

import json
import queue
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import markdown as md
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import ListFlowable, ListItem, Paragraph, Preformatted, SimpleDocTemplate, Spacer
from bs4 import BeautifulSoup, NavigableString, Tag

from src.config import Settings, load_settings
from src.pipeline.cache import clear_cache, get_cache
from src.pipeline.orchestrator import SummaryPipeline
from src.pipeline.queue import run_batch


class SingleSummaryRequest(BaseModel):
    url: str = Field(..., description="单个 B 站视频链接")
    output_dir: str = Field(default="output", description="Markdown 输出目录")
    work_dir: str = Field(default="work", description="临时音频目录")


class BatchSummaryRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, description="待处理的视频链接列表")
    output_dir: str = Field(default="output", description="Markdown 输出目录")
    work_dir: str = Field(default="work", description="临时音频目录")
    max_workers: int | None = Field(default=None, ge=1, description="并发任务数")
    max_retries: int | None = Field(default=None, ge=0, description="单任务重试次数")


class TaskResultPayload(BaseModel):
    url: str
    success: bool
    output_file: str | None = None
    error_message: str | None = None


class SingleSummaryResponse(BaseModel):
    success: bool
    url: str
    output_file: str | None = None
    error_message: str | None = None
    logs: list[str]


class BatchSummaryResponse(BaseModel):
    success_count: int
    failure_count: int
    results: list[TaskResultPayload]
    logs: list[str]


class JobCreateRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, description="需要处理的视频链接")


class JobCreateResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    kind: str
    status: str
    error_message: str | None = None
    output_files: list[str]
    logs: list[str]


class JobCancelResponse(BaseModel):
    job_id: str
    status: str


@dataclass
class JobState:
    job_id: str
    kind: str
    urls: list[str]
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    status: str = "running"
    logs: list[str] = field(default_factory=list)
    output_files: list[str] = field(default_factory=list)
    error_message: str | None = None
    cancel_requested: bool = False
    event_queue: queue.Queue[dict[str, Any]] = field(default_factory=lambda: queue.Queue(maxsize=1000))

    def update_status(self, new_status: str) -> None:
        """Thread-safe status update."""
        with self._lock:
            self.status = new_status

    def set_cancel_requested(self, value: bool) -> None:
        """Thread-safe cancel flag update."""
        with self._lock:
            self.cancel_requested = value

    def is_cancel_requested(self) -> bool:
        """Thread-safe cancel flag read."""
        with self._lock:
            return self.cancel_requested

    def append_log(self, log: str) -> None:
        """Thread-safe log append."""
        with self._lock:
            self.logs.append(log)

    def set_output_files(self, files: list[str]) -> None:
        """Thread-safe output files update."""
        with self._lock:
            self.output_files = files

    def set_error(self, error: str | None) -> None:
        """Thread-safe error message update."""
        with self._lock:
            self.error_message = error

    def emit_event(self, event: dict[str, Any]) -> bool:
        """Emit event to queue, returns False if queue is full."""
        try:
            self.event_queue.put_nowait(event)
            return True
        except queue.Full:
            # Queue is full, drop event to prevent unbounded growth
            return False


app = FastAPI(
    title="Bilibili Summary Service",
    description="通过 HTTP 调用 B 站视频总结能力，并保留原有 CLI 使用方式。",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JOB_STORE: dict[str, JobState] = {}
JOB_STORE_LOCK = threading.Lock()


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_output_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        path = (_backend_root() / path).resolve()
    return path


def _job_logger(job: JobState):
    def _log(message: str) -> None:
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
        job.append_log(line)
        print(line, flush=True)
        job.emit_event({"event": "log", "message": line})

    return _log


def _emit_job_event(job: JobState, event: str, **payload: Any) -> None:
    data = {"event": event}
    data.update(payload)
    job.emit_event(data)


def _render_pdf_from_markdown(markdown_text: str, output_pdf: Path) -> None:
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    # Use built-in CJK CID font to avoid Chinese garbled text in generated PDF.
    font_name = "STSong-Light"
    pdfmetrics.registerFont(UnicodeCIDFont(font_name))

    html = md.markdown(markdown_text, extensions=["fenced_code", "tables", "sane_lists"])
    soup = BeautifulSoup(html, "html.parser")

    doc = SimpleDocTemplate(
        str(output_pdf),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Bilibili Summary",
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="BodyCN",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=11,
            leading=17,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H1CN",
            parent=styles["Heading1"],
            fontName=font_name,
            fontSize=20,
            leading=26,
            spaceBefore=6,
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H2CN",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=16,
            leading=22,
            spaceBefore=6,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H3CN",
            parent=styles["Heading3"],
            fontName=font_name,
            fontSize=14,
            leading=20,
            spaceBefore=5,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="QuoteCN",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=10,
            leading=16,
            textColor="#444444",
            leftIndent=12,
            borderColor="#CCCCCC",
            borderWidth=1,
            borderPadding=6,
            borderLeft=True,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CodeCN",
            parent=styles["Code"],
            fontName=font_name,
            fontSize=9,
            leading=13,
            backColor="#F7F7F7",
            borderColor="#DDDDDD",
            borderWidth=0.5,
            borderPadding=6,
            leftIndent=2,
            rightIndent=2,
            spaceAfter=8,
        )
    )

    def flatten_text(node: Tag | NavigableString) -> str:
        if isinstance(node, NavigableString):
            return str(node)

        if not isinstance(node, Tag):
            return ""

        if node.name == "code":
            return f"<font name=\"{font_name}\">{node.get_text()}</font>"
        if node.name == "strong":
            return f"<b>{''.join(flatten_text(c) for c in node.children)}</b>"
        if node.name == "em":
            return f"<i>{''.join(flatten_text(c) for c in node.children)}</i>"
        if node.name == "a":
            href = node.get("href", "")
            text = ''.join(flatten_text(c) for c in node.children).strip() or href
            return f"<u>{text}</u> ({href})" if href else text
        if node.name == "br":
            return "<br/>"

        return ''.join(flatten_text(c) for c in node.children)

    def build_list(tag: Tag, ordered: bool) -> ListFlowable:
        items: list[ListItem] = []
        for li in tag.find_all("li", recursive=False):
            first_parts: list[str] = []
            nested_lists: list[Tag] = []
            for child in li.children:
                if isinstance(child, Tag) and child.name in {"ul", "ol"}:
                    nested_lists.append(child)
                else:
                    first_parts.append(flatten_text(child))

            item_flowables: list[Any] = [
                Paragraph(''.join(first_parts).strip() or " ", styles["BodyCN"])
            ]

            for nested in nested_lists:
                item_flowables.append(build_list(nested, ordered=(nested.name == "ol")))

            items.append(ListItem(item_flowables))

        return ListFlowable(
            items,
            bulletType="1" if ordered else "bullet",
            start="1",
            leftIndent=16,
            bulletFontName=font_name,
            bulletFontSize=10,
        )

    story: list[Any] = []
    roots = [node for node in soup.contents if not (isinstance(node, NavigableString) and not node.strip())]

    for node in roots:
        if isinstance(node, NavigableString):
            text = str(node).strip()
            if text:
                story.append(Paragraph(text, styles["BodyCN"]))
            continue

        if not isinstance(node, Tag):
            continue

        if node.name == "h1":
            story.append(Paragraph(flatten_text(node), styles["H1CN"]))
        elif node.name == "h2":
            story.append(Paragraph(flatten_text(node), styles["H2CN"]))
        elif node.name == "h3":
            story.append(Paragraph(flatten_text(node), styles["H3CN"]))
        elif node.name == "blockquote":
            story.append(Paragraph(flatten_text(node), styles["QuoteCN"]))
        elif node.name == "pre":
            story.append(Preformatted(node.get_text().rstrip(), styles["CodeCN"]))
        elif node.name == "ul":
            story.append(build_list(node, ordered=False))
            story.append(Spacer(1, 4))
        elif node.name == "ol":
            story.append(build_list(node, ordered=True))
            story.append(Spacer(1, 4))
        elif node.name == "hr":
            story.append(Spacer(1, 10))
        elif node.name == "table":
            # Keep table content readable in plain text when exporting to PDF.
            table_text = ' | '.join(x.get_text(strip=True) for x in node.find_all(["th", "td"]))
            story.append(Paragraph(table_text or " ", styles["BodyCN"]))
        else:
            story.append(Paragraph(flatten_text(node), styles["BodyCN"]))

    if not story:
        story.append(Paragraph(" ", styles["BodyCN"]))

    doc.build(story)


def _build_logger(logs: list[str]):
    def _log(message: str) -> None:
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
        logs.append(line)
        print(line, flush=True)

    return _log


def _build_pipeline(
    output_dir: str,
    work_dir: str,
    logger,
    cancel_checker=None,
) -> tuple[SummaryPipeline, Settings]:
    settings = load_settings(output_dir=Path(output_dir), work_dir=Path(work_dir))
    logger(
        "配置已加载: "
        f"base_url={settings.llm_base_url}, "
        f"chat_path={settings.llm_chat_path}, "
        f"transcribe_path={settings.llm_transcribe_path}, "
        f"summary_model={settings.summary_model}, "
        f"transcribe_model={settings.transcribe_model}, "
        f"use_system_proxy={settings.use_system_proxy}"
    )
    return SummaryPipeline(settings=settings, logger=logger, cancel_checker=cancel_checker), settings


def _run_single_job(job: JobState) -> None:
    logger = _job_logger(job)
    try:
        pipeline, _ = _build_pipeline("output", "work", logger, cancel_checker=job.is_cancel_requested)
        output_file = pipeline.process_url(job.urls[0])
        output_path = _resolve_output_path(output_file)
        job.set_output_files([str(output_path)])
        job.update_status("canceled" if job.is_cancel_requested() else "completed")
        _emit_job_event(job, "result", output_files=job.output_files)
    except Exception as exc:  # noqa: BLE001
        if job.is_cancel_requested() or str(exc) == "任务已取消":
            job.update_status("canceled")
            _emit_job_event(job, "canceled")
        else:
            job.update_status("failed")
            job.set_error(str(exc))
            _emit_job_event(job, "error", message=job.error_message)
    finally:
        _emit_job_event(job, "done", status=job.status)


def _run_batch_job(job: JobState) -> None:
    logger = _job_logger(job)
    try:
        pipeline, settings = _build_pipeline("output", "work", logger, cancel_checker=job.is_cancel_requested)
        report = run_batch(
            urls=job.urls,
            worker=pipeline.process_url,
            max_workers=settings.max_workers,
            max_retries=settings.max_retries,
            logger=logger,
        )
        job.set_output_files([
            str(_resolve_output_path(item.output_file))
            for item in report.results
            if item.success and item.output_file
        ])
        if job.is_cancel_requested():
            job.update_status("canceled")
        else:
            job.update_status("completed" if report.failure_count == 0 else "failed")
        if report.failure_count > 0:
            job.set_error(f"批量任务有失败项: success={report.success_count}, failed={report.failure_count}")
        _emit_job_event(job, "result", output_files=job.output_files)
    except Exception as exc:  # noqa: BLE001
        if job.is_cancel_requested() or str(exc) == "任务已取消":
            job.update_status("canceled")
            _emit_job_event(job, "canceled")
        else:
            job.update_status("failed")
            job.set_error(str(exc))
            _emit_job_event(job, "error", message=job.error_message)
    finally:
        _emit_job_event(job, "done", status=job.status)


def _register_job(kind: str, urls: list[str]) -> JobState:
    job = JobState(job_id=uuid.uuid4().hex, kind=kind, urls=urls)
    with JOB_STORE_LOCK:
        JOB_STORE[job.job_id] = job
    return job


def _get_job_or_404(job_id: str) -> JobState:
    with JOB_STORE_LOCK:
        job = JOB_STORE.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/jobs/single", response_model=JobCreateResponse)
def create_single_job(request: SingleSummaryRequest) -> JobCreateResponse:
    job = _register_job(kind="single", urls=[request.url])
    threading.Thread(target=_run_single_job, args=(job,), daemon=True).start()
    return JobCreateResponse(job_id=job.job_id, status=job.status)


@app.post("/jobs/batch", response_model=JobCreateResponse)
def create_batch_job(request: JobCreateRequest) -> JobCreateResponse:
    job = _register_job(kind="batch", urls=request.urls)
    threading.Thread(target=_run_batch_job, args=(job,), daemon=True).start()
    return JobCreateResponse(job_id=job.job_id, status=job.status)


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str) -> JobStatusResponse:
    job = _get_job_or_404(job_id)
    return JobStatusResponse(
        job_id=job.job_id,
        kind=job.kind,
        status=job.status,
        error_message=job.error_message,
        output_files=job.output_files,
        logs=job.logs,
    )


@app.post("/jobs/{job_id}/cancel", response_model=JobCancelResponse)
def cancel_job(job_id: str) -> JobCancelResponse:
    job = _get_job_or_404(job_id)
    job.set_cancel_requested(True)
    if job.status == "running":
        job.update_status("canceled")
        _emit_job_event(job, "log", message=f"[{datetime.now().strftime('%H:%M:%S')}] 已收到取消请求，任务已标记为取消")
        _emit_job_event(job, "canceled")
        _emit_job_event(job, "done", status="canceled")
    return JobCancelResponse(job_id=job.job_id, status=job.status)


@app.get("/jobs/{job_id}/stream")
def stream_job(job_id: str) -> StreamingResponse:
    job = _get_job_or_404(job_id)

    def event_generator():
        for line in job.logs:
            payload = json.dumps({"event": "log", "message": line}, ensure_ascii=False)
            yield f"data: {payload}\n\n"

        while True:
            try:
                event = job.event_queue.get(timeout=1)
            except queue.Empty:
                if job.status in {"completed", "failed", "canceled"}:
                    payload = json.dumps({"event": "done", "status": job.status}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                    break
                continue

            payload = json.dumps(event, ensure_ascii=False)
            yield f"data: {payload}\n\n"
            if event.get("event") == "done":
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/jobs/{job_id}/markdown")
def get_job_markdown(job_id: str) -> dict[str, str]:
    job = _get_job_or_404(job_id)
    if not job.output_files:
        raise HTTPException(status_code=404, detail="Markdown output not found")

    md_path = Path(job.output_files[0])
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="Markdown file missing")

    return {"content": md_path.read_text(encoding="utf-8"), "file_name": md_path.name}


@app.get("/jobs/{job_id}/download/md")
def download_markdown(job_id: str) -> FileResponse:
    job = _get_job_or_404(job_id)
    if not job.output_files:
        raise HTTPException(status_code=404, detail="Markdown output not found")

    md_path = Path(job.output_files[0])
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="Markdown file missing")

    return FileResponse(path=str(md_path), filename=md_path.name, media_type="text/markdown")


@app.get("/jobs/{job_id}/download/pdf")
def download_pdf(job_id: str) -> FileResponse:
    job = _get_job_or_404(job_id)
    if not job.output_files:
        raise HTTPException(status_code=404, detail="Markdown output not found")

    md_path = Path(job.output_files[0])
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="Markdown file missing")

    pdf_path = md_path.with_suffix(".pdf")
    markdown_text = md_path.read_text(encoding="utf-8")
    _render_pdf_from_markdown(markdown_text=markdown_text, output_pdf=pdf_path)

    return FileResponse(path=str(pdf_path), filename=pdf_path.name, media_type="application/pdf")


@app.post("/summaries/single", response_model=SingleSummaryResponse)
async def summarize_single(request: SingleSummaryRequest) -> SingleSummaryResponse:
    logs: list[str] = []
    logger = _build_logger(logs)

    try:
        pipeline, _ = _build_pipeline(request.output_dir, request.work_dir, logger)
        output_file = await run_in_threadpool(pipeline.process_url, request.url)
        return SingleSummaryResponse(
            success=True,
            url=request.url,
            output_file=output_file,
            logs=logs,
        )
    except Exception as exc:  # noqa: BLE001
        logger(f"任务失败: {request.url} -> {exc}")
        return SingleSummaryResponse(
            success=False,
            url=request.url,
            error_message=str(exc),
            logs=logs,
        )


@app.post("/summaries/batch", response_model=BatchSummaryResponse)
async def summarize_batch(request: BatchSummaryRequest) -> BatchSummaryResponse:
    logs: list[str] = []
    logger = _build_logger(logs)

    try:
        pipeline, settings = _build_pipeline(request.output_dir, request.work_dir, logger)
        max_workers = request.max_workers or settings.max_workers
        max_retries = request.max_retries if request.max_retries is not None else settings.max_retries

        report = await run_in_threadpool(
            run_batch,
            request.urls,
            pipeline.process_url,
            max_workers,
            max_retries,
            logger,
        )

        results = [
            TaskResultPayload(
                url=item.url,
                success=item.success,
                output_file=item.output_file,
                error_message=item.error_message,
            )
            for item in report.results
        ]

        return BatchSummaryResponse(
            success_count=report.success_count,
            failure_count=report.failure_count,
            results=results,
            logs=logs,
        )
    except Exception as exc:  # noqa: BLE001
        logger(f"批量任务异常: {exc}")
        return BatchSummaryResponse(
            success_count=0,
            failure_count=len(request.urls),
            results=[
                TaskResultPayload(
                    url=url,
                    success=False,
                    error_message=str(exc),
                )
                for url in request.urls
            ],
            logs=logs,
        )


@app.get("/cache/stats")
def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics."""
    cache = get_cache()
    return cache.get_stats()


@app.post("/cache/clear")
def clear_cache_endpoint() -> dict[str, str]:
    """Clear all cached results."""
    clear_cache()
    return {"status": "ok", "message": "Cache cleared"}
