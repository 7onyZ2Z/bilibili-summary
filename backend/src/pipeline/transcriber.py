from __future__ import annotations

import subprocess
from pathlib import Path
from shutil import rmtree
from typing import Callable

import requests


class TranscriptionError(RuntimeError):
    pass


class OpenAITranscriber:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        transcribe_path: str,
        model: str,
        timeout_seconds: int,
        max_upload_mb: int,
        segment_seconds: int,
        use_system_proxy: bool,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.transcribe_path = transcribe_path if transcribe_path.startswith("/") else f"/{transcribe_path}"
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_upload_mb = max_upload_mb
        self.segment_seconds = segment_seconds
        self.logger = logger
        self._use_system_proxy = use_system_proxy
        self._session: requests.Session | None = None

    @property
    def session(self) -> requests.Session:
        """Lazy initialization of session with proper cleanup support."""
        if self._session is None:
            self._session = requests.Session()
            self._session.trust_env = self._use_system_proxy
        return self._session

    def close(self) -> None:
        """Explicitly close the HTTP session to release resources."""
        if self._session is not None:
            self._session.close()
            self._session = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __del__(self):
        """Ensure session is closed on object destruction."""
        self.close()

    def _log(self, message: str) -> None:
        if self.logger:
            self.logger(message)

    def _transcribe_single_file(self, audio_file: Path, endpoint: str) -> str:
        with audio_file.open("rb") as fp:
            response = self.session.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                },
                data={
                    "model": self.model,
                },
                files={
                    "file": (audio_file.name, fp, "audio/mpeg"),
                },
                timeout=(10, self.timeout_seconds),
            )
            response.raise_for_status()
            payload = response.json()

        text = str(payload.get("text", "")).strip()
        if not text:
            raise TranscriptionError(f"Transcription response was empty from {endpoint}.")
        return text

    def _split_audio(self, audio_file: Path) -> list[Path]:
        chunk_dir = audio_file.parent / f"{audio_file.stem}_chunks"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        output_pattern = str(chunk_dir / "chunk_%03d.mp3")

        # Re-encode while splitting to keep chunk uploads stable.
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(audio_file),
            "-f",
            "segment",
            "-segment_time",
            str(self.segment_seconds),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            "64k",
            output_pattern,
        ]

        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except Exception as exc:  # noqa: BLE001
            raise TranscriptionError(f"Failed to split audio for chunked transcription: {exc}") from exc

        chunks = sorted(chunk_dir.glob("chunk_*.mp3"))
        if not chunks:
            raise TranscriptionError("No chunk files were created during audio split.")
        return chunks

    def transcribe(self, audio_file: Path) -> str:
        if not audio_file.exists():
            raise TranscriptionError(f"Audio file not found: {audio_file}")

        endpoint = f"{self.base_url}{self.transcribe_path}"
        audio_size_mb = audio_file.stat().st_size / (1024 * 1024)
        try:
            if audio_size_mb <= self.max_upload_mb:
                return self._transcribe_single_file(audio_file, endpoint)

            self._log(
                f"检测到大音频文件 {audio_size_mb:.2f} MB，超过阈值 {self.max_upload_mb} MB，"
                f"开始分段转写（segment={self.segment_seconds}s）。"
            )
            chunks = self._split_audio(audio_file)
            merged_text = []

            for index, chunk_file in enumerate(chunks, start=1):
                chunk_size_mb = chunk_file.stat().st_size / (1024 * 1024)
                self._log(f"转写分段 {index}/{len(chunks)}: {chunk_file.name} ({chunk_size_mb:.2f} MB)")
                merged_text.append(self._transcribe_single_file(chunk_file, endpoint))

            chunk_dir = chunks[0].parent if chunks else None
            if chunk_dir and chunk_dir.exists():
                try:
                    rmtree(chunk_dir)
                except OSError as exc:
                    self._log(f"警告：清理临时文件失败 {chunk_dir}: {exc}")

            return "\n".join(part for part in merged_text if part.strip())
        except requests.Timeout as exc:
            raise TranscriptionError(
                f"Transcription timed out via {endpoint}. "
                f"Current read timeout is {self.timeout_seconds}s."
            ) from exc
        except requests.HTTPError as exc:
            response_text = ""
            if exc.response is not None:
                response_text = exc.response.text[:300]
            raise TranscriptionError(
                f"Transcription HTTP error via {endpoint}: {exc}. Response: {response_text}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise TranscriptionError(f"Transcription failed via {endpoint}: {exc}") from exc
