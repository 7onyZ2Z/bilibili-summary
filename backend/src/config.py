from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    llm_base_url: str
    llm_chat_path: str
    llm_transcribe_path: str
    summary_model: str
    transcribe_model: str
    max_retries: int
    max_workers: int
    request_timeout_seconds: int
    summary_timeout_seconds: int
    transcribe_timeout_seconds: int
    transcribe_max_upload_mb: int
    transcribe_segment_seconds: int
    download_socket_timeout_seconds: int
    download_retries: int
    download_fragment_concurrency: int
    download_use_aria2c: bool
    use_system_proxy: bool
    keep_temp_files: bool
    output_dir: Path
    work_dir: Path


def _parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings(output_dir: Path | None = None, work_dir: Path | None = None) -> Settings:
    load_dotenv()

    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY is required. Please set it in your environment or .env file.")

    resolved_output_dir = output_dir or Path("output")
    resolved_work_dir = work_dir or Path("work")

    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    resolved_work_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        openai_api_key=openai_api_key,
        llm_base_url=os.getenv("LLM_BASE_URL", "https://yunwu.ai").rstrip("/"),
        llm_chat_path=os.getenv("LLM_CHAT_PATH", "/v1/chat/completions"),
        llm_transcribe_path=os.getenv("LLM_TRANSCRIBE_PATH", "/v1/audio/transcriptions"),
        summary_model=os.getenv("SUMMARY_MODEL", "qwen3-vl-30b-a3b-instruct"),
        transcribe_model=os.getenv("TRANSCRIBE_MODEL", "whisper-1"),
        max_retries=int(os.getenv("MAX_RETRIES", "2")),
        max_workers=max(1, int(os.getenv("MAX_WORKERS", "2"))),
        request_timeout_seconds=max(5, int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))),
        summary_timeout_seconds=max(10, int(os.getenv("SUMMARY_TIMEOUT_SECONDS", "120"))),
        transcribe_timeout_seconds=max(30, int(os.getenv("TRANSCRIBE_TIMEOUT_SECONDS", "600"))),
        transcribe_max_upload_mb=max(1, int(os.getenv("TRANSCRIBE_MAX_UPLOAD_MB", "20"))),
        transcribe_segment_seconds=max(60, int(os.getenv("TRANSCRIBE_SEGMENT_SECONDS", "600"))),
        download_socket_timeout_seconds=max(10, int(os.getenv("DOWNLOAD_SOCKET_TIMEOUT_SECONDS", "45"))),
        download_retries=max(1, int(os.getenv("DOWNLOAD_RETRIES", "10"))),
        download_fragment_concurrency=max(1, int(os.getenv("DOWNLOAD_FRAGMENT_CONCURRENCY", "8"))),
        download_use_aria2c=_parse_bool(os.getenv("DOWNLOAD_USE_ARIA2C", "true"), default=True),
        use_system_proxy=_parse_bool(os.getenv("USE_SYSTEM_PROXY", "false"), default=False),
        keep_temp_files=_parse_bool(os.getenv("KEEP_TEMP_FILES", "false"), default=False),
        output_dir=resolved_output_dir,
        work_dir=resolved_work_dir,
    )
