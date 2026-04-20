from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class VideoMetadata:
    video_id: str
    title: str
    owner_name: str
    publish_time: datetime | None
    source_url: str


@dataclass(frozen=True)
class InterviewQA:
    question: str
    answer: str


@dataclass(frozen=True)
class SummaryResult:
    bagu_topic: str
    key_points: list[str]
    interview_qas: list[InterviewQA]


@dataclass(frozen=True)
class TaskResult:
    url: str
    success: bool
    output_file: str | None = None
    error_message: str | None = None


@dataclass
class BatchRunReport:
    results: list[TaskResult] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return sum(1 for item in self.results if item.success)

    @property
    def failure_count(self) -> int:
        return sum(1 for item in self.results if not item.success)
