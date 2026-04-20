from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from src.models import BatchRunReport, TaskResult


def _run_with_retry(
    url: str,
    worker: Callable[[str], str],
    max_retries: int,
    logger: Callable[[str], None] | None = None,
) -> TaskResult:
    last_error = None
    for attempt in range(max_retries + 1):
        if logger:
            logger(f"任务开始: {url} (attempt {attempt + 1}/{max_retries + 1})")
        try:
            output = worker(url)
            return TaskResult(url=url, success=True, output_file=output)
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            if logger:
                logger(f"任务失败: {url} (attempt {attempt + 1}/{max_retries + 1}) -> {last_error}")
            if attempt < max_retries:
                time.sleep(1.2 * (attempt + 1))

    return TaskResult(url=url, success=False, error_message=last_error or "Unknown error")


def run_batch(
    urls: list[str],
    worker: Callable[[str], str],
    max_workers: int,
    max_retries: int,
    logger: Callable[[str], None] | None = None,
) -> BatchRunReport:
    report = BatchRunReport()
    if not urls:
        return report

    if logger:
        logger(f"批量任务启动: total={len(urls)}, workers={max(1, max_workers)}, retries={max_retries}")

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        future_map = {
            executor.submit(_run_with_retry, url, worker, max_retries, logger): url
            for url in urls
        }
        for future in as_completed(future_map):
            result = future.result()
            report.results.append(result)
            if logger:
                status = "SUCCESS" if result.success else "FAILED"
                logger(f"任务结束: {future_map[future]} -> {status}")

    if logger:
        logger(f"批量任务完成: success={report.success_count}, failed={report.failure_count}")

    return report
