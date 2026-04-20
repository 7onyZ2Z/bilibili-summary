from __future__ import annotations

import json
from typing import Any

import requests

from src.models import InterviewQA, SummaryResult, VideoMetadata


class SummaryError(RuntimeError):
    pass


class OpenAISummarizer:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        chat_path: str,
        model: str,
        timeout_seconds: int,
        use_system_proxy: bool,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.chat_path = chat_path if chat_path.startswith("/") else f"/{chat_path}"
        self.model = model
        self.timeout_seconds = timeout_seconds
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

    def summarize(self, metadata: VideoMetadata, transcript: str) -> SummaryResult:
        system_prompt = (
            "你是一名面试笔记整理助手。"
            "你的任务是从视频转写文本中提炼可用于面试准备的高质量笔记，"
            "并严格遵循用户指定的输出结构。"
            "你必须只输出合法 JSON，不要输出任何多余文本。"
        )

        user_prompt = f"""
请根据以下视频信息与转写内容，生成“面向面试准备”的结构化笔记。

视频标题：{metadata.title}
UP主：{metadata.owner_name}
来源链接：{metadata.source_url}

转写文本：
{transcript}

请严格按下面的 JSON 结构返回：
{{
  "bagu_topic": "字符串，仅一个词，用于概括视频重点讲解方向",
  "key_points": ["字符串", "..."],
  "interview_qas": [{{"question": "字符串", "answer": "字符串"}}],
}}

要求：
1) 聚焦可落地的面试知识，不要写泛泛而谈的总结。
2) key_points 数量控制在 3 到 8 条。
3) interview_qas 数量控制在 3 到 8 组，且必须是“面试官问题 + 候选人回答”风格。
4) 回答必须同时满足“专业术语准确”和“口语化表达自然”，避免生硬书面腔。
5) 若转写质量较差，可谨慎推断，并在内容中标注不确定性。
6) 尽量保留原文术语和关键词。
""".strip()

        try:
            response = self.session.post(
                f"{self.base_url}{self.chat_path}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                },
                timeout=(10, self.timeout_seconds),
            )
            response.raise_for_status()
            response_data = response.json()
            content = (
                response_data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "{}")
            )
            payload = json.loads(content)
        except requests.Timeout as exc:
            raise SummaryError(
                f"总结接口超时: {self.base_url}{self.chat_path}，"
                f"当前读取超时 {self.timeout_seconds}s。"
            ) from exc
        except requests.HTTPError as exc:
            response_text = ""
            if exc.response is not None:
                response_text = exc.response.text[:300]
            raise SummaryError(
                f"总结接口 HTTP 错误: {exc}，返回片段: {response_text}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise SummaryError(f"总结生成失败: {exc}") from exc

        return self._validate_payload(payload)

    def _validate_payload(self, payload: dict[str, Any]) -> SummaryResult:
        bagu_topic = str(payload.get("bagu_topic", "")).strip()
        key_points = [str(item).strip() for item in payload.get("key_points", []) if str(item).strip()]

        qa_items = []
        for raw in payload.get("interview_qas", []):
            question = str(raw.get("question", "")).strip()
            answer = str(raw.get("answer", "")).strip()
            if question and answer:
                qa_items.append(InterviewQA(question=question, answer=answer))

        if not bagu_topic:
            bagu_topic = "未知"
        if not key_points:
            key_points = ["未提取到有效知识点。"]
        if not qa_items:
            qa_items = [
                InterviewQA(
                    question="这条视频里最关键的知识点是什么？",
                    answer="当前转写文本信息不足，无法给出高置信度回答。",
                )
            ]

        return SummaryResult(
            bagu_topic=bagu_topic,
            key_points=key_points,
            interview_qas=qa_items,
        )
