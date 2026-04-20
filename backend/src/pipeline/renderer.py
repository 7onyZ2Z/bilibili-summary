from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.models import SummaryResult, VideoMetadata


def _safe_filename(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return normalized[:80] or "untitled"


class MarkdownRenderer:
    def __init__(self, template_dir: Path, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(enabled_extensions=()),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_to_file(
        self,
        metadata: VideoMetadata,
        transcript: str,
        summary: SummaryResult,
    ) -> Path:
        template = self.env.get_template("summary.md.j2")
        markdown = template.render(
            generated_at=datetime.now(tz=timezone.utc).isoformat(),
            metadata=metadata,
            transcript=transcript,
            summary=summary,
        )

        file_name = f"{_safe_filename(metadata.video_id)}_{_safe_filename(metadata.title)}_summary.md"
        output_path = self.output_dir / file_name
        output_path.write_text(markdown, encoding="utf-8")
        return output_path
