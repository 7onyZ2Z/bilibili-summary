from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.config import Settings
from src.pipeline.cache import get_cache
from src.pipeline.downloader import AudioDownloader
from src.pipeline.parser import fetch_video_metadata
from src.pipeline.renderer import MarkdownRenderer
from src.pipeline.summarizer import OpenAISummarizer
from src.pipeline.transcriber import OpenAITranscriber


class SummaryPipeline:
    def __init__(
        self,
        settings: Settings,
        logger: Callable[[str], None] | None = None,
        cancel_checker: Callable[[], bool] | None = None,
    ) -> None:
        self.settings = settings
        self.logger = logger
        self.cancel_checker = cancel_checker
        self.downloader = AudioDownloader(
            work_dir=settings.work_dir,
            socket_timeout_seconds=settings.download_socket_timeout_seconds,
            retries=settings.download_retries,
            fragment_concurrency=settings.download_fragment_concurrency,
            use_aria2c=settings.download_use_aria2c,
            logger=self.logger,
        )
        self.transcriber = OpenAITranscriber(
            api_key=settings.openai_api_key,
            base_url=settings.llm_base_url,
            transcribe_path=settings.llm_transcribe_path,
            model=settings.transcribe_model,
            timeout_seconds=settings.transcribe_timeout_seconds,
            max_upload_mb=settings.transcribe_max_upload_mb,
            segment_seconds=settings.transcribe_segment_seconds,
            use_system_proxy=settings.use_system_proxy,
            logger=self.logger,
        )
        self.summarizer = OpenAISummarizer(
            api_key=settings.openai_api_key,
            base_url=settings.llm_base_url,
            chat_path=settings.llm_chat_path,
            model=settings.summary_model,
            timeout_seconds=settings.summary_timeout_seconds,
            use_system_proxy=settings.use_system_proxy,
        )
        self.renderer = MarkdownRenderer(template_dir=Path("templates"), output_dir=settings.output_dir)

    def _log(self, message: str) -> None:
        if self.logger:
            self.logger(message)

    def _check_cancel(self) -> None:
        if self.cancel_checker and self.cancel_checker():
            raise RuntimeError("任务已取消")

    def process_url(self, url: str) -> str:
        self._check_cancel()

        # Check cache first
        cache = get_cache(self.settings.output_dir / ".cache")
        cached_result = cache.get(url)
        if cached_result:
            self._log(f"使用缓存结果: {cached_result}")
            # Verify the cached file still exists
            if Path(cached_result).exists():
                return cached_result
            else:
                self._log("缓存文件不存在，将重新处理")

        self._log(f"开始处理视频: {url}")
        self._log("步骤 1/5: 解析链接与拉取视频元数据")
        metadata = fetch_video_metadata(url, timeout_seconds=self.settings.request_timeout_seconds)

        self._check_cancel()
        self._log(f"步骤 2/5: 下载音频 (video_id={metadata.video_id})")
        audio_path = self.downloader.download_audio(metadata.source_url, metadata.video_id)

        self._check_cancel()
        file_size_mb = audio_path.stat().st_size / (1024 * 1024)
        self._log(
            f"步骤 3/5: 音频转写 ({audio_path.name}, {file_size_mb:.2f} MB, "
            f"timeout={self.settings.transcribe_timeout_seconds}s)"
        )
        transcript = self.transcriber.transcribe(audio_path)

        self._check_cancel()
        self._log(
            f"步骤 4/5: 生成总结与面试问答 "
            f"(model={self.settings.summary_model}, timeout={self.settings.summary_timeout_seconds}s)"
        )
        summary = self.summarizer.summarize(metadata=metadata, transcript=transcript)

        self._check_cancel()
        self._log("步骤 5/5: 渲染并写入 Markdown")
        output_path = self.renderer.render_to_file(metadata=metadata, transcript=transcript, summary=summary)

        if not self.settings.keep_temp_files and audio_path.exists():
            audio_path.unlink(missing_ok=True)
            self._log(f"已清理临时音频: {audio_path}")

        # Cache the result
        cache.put(
            url=url,
            output_path=str(output_path),
            video_id=metadata.video_id,
            metadata={
                "title": metadata.title,
                "owner_name": metadata.owner_name,
            },
        )
        self._log(f"已缓存处理结果: {url}")

        self._log(f"处理完成: {output_path}")
        return str(output_path)

    def close(self) -> None:
        """Clean up resources held by the pipeline and its components."""
        self.transcriber.close()
        self.summarizer.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
