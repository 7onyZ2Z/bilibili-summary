#!/usr/bin/env python3
"""诊断脚本 - 测试各个组件是否正常工作"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import load_settings
from src.pipeline.parser import fetch_video_metadata
from src.pipeline.downloader import AudioDownloader


def test_config():
    print("1. 测试配置加载...")
    try:
        settings = load_settings()
        print(f"   ✓ API Key: {'已设置' if settings.openai_api_key else '未设置'}")
        print(f"   ✓ Base URL: {settings.llm_base_url}")
        print(f"   ✓ Chat Path: {settings.llm_chat_path}")
        print(f"   ✓ Transcribe Path: {settings.llm_transcribe_path}")
        return settings
    except Exception as e:
        print(f"   ✗ 配置加载失败: {e}")
        return None


def test_bilibili_api(url: str):
    print(f"\n2. 测试 Bilibili API...")
    try:
        metadata = fetch_video_metadata(url, timeout_seconds=20)
        print(f"   ✓ 视频ID: {metadata.video_id}")
        print(f"   ✓ 标题: {metadata.title[:50]}...")
        print(f"   ✓ 作者: {metadata.owner_name}")
        return metadata
    except Exception as e:
        print(f"   ✗ Bilibili API 失败: {e}")
        return None


def test_llm_endpoints(settings):
    print(f"\n3. 测试 LLM API 端点...")
    import requests

    session = requests.Session()
    session.trust_env = settings.use_system_proxy

    endpoints = [
        ("Chat", f"{settings.llm_base_url}{settings.llm_chat_path}"),
        ("Transcribe", f"{settings.llm_base_url}{settings.llm_transcribe_path}"),
    ]

    for name, url in endpoints:
        try:
            resp = session.head(url, timeout=10)
            if resp.status_code == 405:  # Method Not Allowed is OK for POST endpoints
                print(f"   ✓ {name} 端点存在 (HTTP {resp.status_code})")
            elif resp.status_code == 404:
                print(f"   ✗ {name} 端点不存在 (HTTP 404)")
                print(f"      URL: {url}")
            else:
                print(f"   ? {name} 端点状态: HTTP {resp.status_code}")
        except requests.exceptions.Timeout:
            print(f"   ✗ {name} 端点超时")
        except requests.exceptions.ConnectionError as e:
            print(f"   ✗ {name} 端点连接失败: {e}")
        except Exception as e:
            print(f"   ✗ {name} 端点错误: {e}")


def test_audio_download(metadata: object, settings):
    print(f"\n4. 测试音频下载...")
    try:
        downloader = AudioDownloader(
            work_dir=settings.work_dir,
            socket_timeout_seconds=settings.download_socket_timeout_seconds,
            retries=2,  # 减少重试次数以加快测试
            fragment_concurrency=settings.download_fragment_concurrency,
            use_aria2c=settings.download_use_aria2c,
            logger=lambda msg: print(f"      {msg}"),
        )
        audio_path = downloader.download_audio(metadata.source_url, metadata.video_id)
        print(f"   ✓ 音频下载成功: {audio_path}")
        print(f"   ✓ 文件大小: {audio_path.stat().st_size / (1024*1024):.2f} MB")
        return audio_path
    except Exception as e:
        print(f"   ✗ 音频下载失败: {e}")
        return None


def main():
    test_url = "https://www.bilibili.com/video/BV1xx411c7XD"  # 测试视频

    print("=" * 60)
    print("Bilibili Summary 诊断工具")
    print("=" * 60)

    settings = test_config()
    if not settings:
        print("\n❌ 配置测试失败，请检查 .env 文件")
        return 1

    metadata = test_bilibili_api(test_url)
    if not metadata:
        print("\n❌ Bilibili API 测试失败")
        return 1

    test_llm_endpoints(settings)

    audio_path = test_audio_download(metadata, settings)

    print("\n" + "=" * 60)
    if audio_path:
        print("✓ 基础组件测试通过")
        print("\n建议：")
        print("1. 检查 LLM API 端点配置是否正确")
        print("2. 确认 API Key 是否有效")
        print("3. 测试完整的处理流程")
    else:
        print("❌ 部分组件测试失败")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
