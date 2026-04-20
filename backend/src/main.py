from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from src.config import load_settings
from src.pipeline.orchestrator import SummaryPipeline
from src.pipeline.queue import run_batch


def _log(message: str) -> None:
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {message}", flush=True)


def _load_urls_from_file(file_path: Path) -> list[str]:
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    urls = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            urls.append(value)
    return urls


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bili-summary",
        description="Generate interview-focused markdown notes from bilibili video links.",
    )
    parser.add_argument("--output-dir", default="output", help="Where markdown files are written.")
    parser.add_argument("--work-dir", default="work", help="Where temporary audio files are stored.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    single = subparsers.add_parser("single", help="Process one bilibili URL.")
    single.add_argument("url", help="A bilibili video URL.")

    batch = subparsers.add_parser("batch", help="Process URLs from a file.")
    batch.add_argument("--input", required=True, help="Path to a text file with one URL per line.")

    return parser


def main() -> int:
    parser = build_cli()
    args = parser.parse_args()

    try:
        settings = load_settings(output_dir=Path(args.output_dir), work_dir=Path(args.work_dir))
        _log(
            "配置已加载: "
            f"base_url={settings.llm_base_url}, "
            f"chat_path={settings.llm_chat_path}, "
            f"transcribe_path={settings.llm_transcribe_path}, "
            f"summary_model={settings.summary_model}, "
            f"transcribe_model={settings.transcribe_model}, "
            f"use_system_proxy={settings.use_system_proxy}, "
            f"download_timeout={settings.download_socket_timeout_seconds}s, "
            f"download_retries={settings.download_retries}, "
            f"download_fragments={settings.download_fragment_concurrency}, "
            f"download_aria2c={settings.download_use_aria2c}"
        )
        pipeline = SummaryPipeline(settings=settings, logger=_log)

        if args.command == "single":
            output = pipeline.process_url(args.url)
            print(f"SUCCESS: {args.url}")
            print(f"OUTPUT: {output}")
            return 0

        urls = _load_urls_from_file(Path(args.input))
        report = run_batch(
            urls=urls,
            worker=pipeline.process_url,
            max_workers=settings.max_workers,
            max_retries=settings.max_retries,
            logger=_log,
        )

        for item in report.results:
            if item.success:
                print(f"SUCCESS: {item.url}")
                print(f"OUTPUT: {item.output_file}")
            else:
                print(f"FAILED: {item.url}")
                print(f"ERROR: {item.error_message}")

        print(f"DONE: success={report.success_count}, failed={report.failure_count}")
        return 0 if report.failure_count == 0 else 2
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
