from __future__ import annotations

from pathlib import Path
from shutil import which
from typing import Callable

import yt_dlp


class DownloadError(RuntimeError):
    pass


class AudioDownloader:
    def __init__(
        self,
        work_dir: Path,
        socket_timeout_seconds: int,
        retries: int,
        fragment_concurrency: int,
        use_aria2c: bool,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.socket_timeout_seconds = socket_timeout_seconds
        self.retries = retries
        self.fragment_concurrency = fragment_concurrency
        self.use_aria2c = use_aria2c
        self.logger = logger
        self.aria2c_path = which("aria2c")

    def _log(self, message: str) -> None:
        if self.logger:
            self.logger(message)

    def _build_options(self, output_template: str, format_selector: str) -> dict:
        options = {
            "format": format_selector,
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "retries": self.retries,
            "fragment_retries": self.retries,
            "extractor_retries": max(3, self.retries // 2),
            "concurrent_fragment_downloads": self.fragment_concurrency,
            "socket_timeout": self.socket_timeout_seconds,
            "force_ipv4": True,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.bilibili.com/",
            },
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }

        if self.use_aria2c and self.aria2c_path:
            options["external_downloader"] = "aria2c"
            options["external_downloader_args"] = [
                "-x", str(max(4, self.fragment_concurrency)),
                "-s", str(max(4, self.fragment_concurrency)),
                "-k", "1M",
                "--timeout", str(self.socket_timeout_seconds),
                "--connect-timeout", "15",
                "--retry-wait", "2",
                "--max-tries", "0",
            ]

        return options

    def download_audio(self, source_url: str, video_id: str) -> Path:
        output_template = str(self.work_dir / f"{video_id}.%(ext)s")
        format_candidates = [
            "bestaudio[acodec!=none]/bestaudio/best",
            "worstaudio[acodec!=none]/worstaudio/bestaudio",
        ]

        last_error = None
        for index, format_selector in enumerate(format_candidates, start=1):
            try:
                self._log(
                    f"下载尝试 {index}/{len(format_candidates)}: format={format_selector}, "
                    f"timeout={self.socket_timeout_seconds}s, retries={self.retries}, "
                    f"aria2c={'on' if (self.use_aria2c and self.aria2c_path) else 'off'}"
                )
                options = self._build_options(output_template=output_template, format_selector=format_selector)
                with yt_dlp.YoutubeDL(options) as ydl:
                    ydl.extract_info(source_url, download=True)

                final_path = self.work_dir / f"{video_id}.mp3"
                if final_path.exists():
                    return final_path
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                self._log(f"下载尝试 {index} 失败: {exc}")

        final_path = self.work_dir / f"{video_id}.mp3"
        if not final_path.exists():
            raise DownloadError(
                "Failed to download audio from source URL after multiple attempts. "
                "This is usually caused by transient Bilibili network throttling, anti-crawler limits, or unstable route to media CDN. "
                f"Last error: {last_error}. Ensure ffmpeg is installed."
            )

        return final_path
