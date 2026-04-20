"""Caching layer for video processing results."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 days
DEFAULT_MAX_CACHE_SIZE_MB = 500


@dataclass
class CacheEntry:
    """A cached result entry."""
    url: str
    output_path: str
    timestamp: float
    video_id: str
    metadata: dict[str, Any]

    def is_expired(self, ttl_seconds: float) -> bool:
        """Check if this cache entry has expired."""
        return time.time() - self.timestamp > ttl_seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "url": self.url,
            "output_path": self.output_path,
            "timestamp": self.timestamp,
            "video_id": self.video_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CacheEntry:
        """Create from dictionary."""
        return cls(
            url=data["url"],
            output_path=data["output_path"],
            timestamp=data["timestamp"],
            video_id=data["video_id"],
            metadata=data["metadata"],
        )


class ResultCache:
    """Cache for video processing results."""

    def __init__(
        self,
        cache_dir: Path,
        ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
        max_cache_size_mb: int = DEFAULT_MAX_CACHE_SIZE_MB,
    ) -> None:
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.max_cache_size_mb = max_cache_size_mb
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self.cache_dir / "cache_index.json"
        self._index: dict[str, CacheEntry] = {}
        self._load_index()

    def _load_index(self) -> None:
        """Load cache index from disk."""
        if not self._index_file.exists():
            return

        try:
            data = json.loads(self._index_file.read_text(encoding="utf-8"))
            self._index = {
                key: CacheEntry.from_dict(entry)
                for key, entry in data.items()
            }
        except (json.JSONDecodeError, KeyError):
            # Invalid cache index, start fresh
            self._index = {}

    def _save_index(self) -> None:
        """Save cache index to disk."""
        data = {
            key: entry.to_dict()
            for key, entry in self._index.items()
        }
        self._index_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _get_cache_key(self, url: str) -> str:
        """Generate cache key from URL."""
        return hashlib.md5(url.encode()).hexdigest()

    def _cleanup_expired(self) -> None:
        """Remove expired entries from cache."""
        expired_keys = [
            key for key, entry in self._index.items()
            if entry.is_expired(self.ttl_seconds)
        ]
        for key in expired_keys:
            self._remove_entry(key)

    def _cleanup_by_size(self) -> None:
        """Remove oldest entries if cache exceeds size limit."""
        total_size_mb = sum(
            Path(entry.output_path).stat().st_size / (1024 * 1024)
            for entry in self._index.values()
            if Path(entry.output_path).exists()
        )

        if total_size_mb <= self.max_cache_size_mb:
            return

        # Sort by timestamp (oldest first) and remove until under limit
        sorted_entries = sorted(self._index.items(), key=lambda x: x[1].timestamp)
        for key, _ in sorted_entries:
            if total_size_mb <= self.max_cache_size_mb * 0.8:  # Leave 20% headroom
                break
            entry = self._index[key]
            path = Path(entry.output_path)
            if path.exists():
                total_size_mb -= path.stat().st_size / (1024 * 1024)
            self._remove_entry(key)

    def _remove_entry(self, key: str) -> None:
        """Remove a cache entry."""
        if key not in self._index:
            return

        entry = self._index[key]
        output_path = Path(entry.output_path)

        # Remove cached markdown file
        if output_path.exists():
            try:
                output_path.unlink()
            except OSError:
                pass  # File may have been removed externally

        del self._index[key]

    def get(self, url: str) -> str | None:
        """Get cached result for URL, if available and not expired."""
        self._cleanup_expired()

        key = self._get_cache_key(url)
        entry = self._index.get(key)

        if not entry:
            return None

        if entry.is_expired(self.ttl_seconds):
            self._remove_entry(key)
            self._save_index()
            return None

        # Verify output file still exists
        if not Path(entry.output_path).exists():
            self._remove_entry(key)
            self._save_index()
            return None

        return entry.output_path

    def put(
        self,
        url: str,
        output_path: str,
        video_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Cache a processing result."""
        self._cleanup_by_size()

        key = self._get_cache_key(url)
        entry = CacheEntry(
            url=url,
            output_path=output_path,
            timestamp=time.time(),
            video_id=video_id,
            metadata=metadata or {},
        )

        self._index[key] = entry
        self._save_index()

    def clear(self) -> None:
        """Clear all cached entries."""
        for key in list(self._index.keys()):
            self._remove_entry(key)
        self._save_index()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_size_mb = sum(
            Path(entry.output_path).stat().st_size / (1024 * 1024)
            for entry in self._index.values()
            if Path(entry.output_path).exists()
        )
        return {
            "entry_count": len(self._index),
            "total_size_mb": round(total_size_mb, 2),
            "max_size_mb": self.max_cache_size_mb,
            "ttl_seconds": self.ttl_seconds,
        }


# Global cache instance (will be initialized when needed)
_global_cache: ResultCache | None = None


def get_cache(cache_dir: Path | None = None) -> ResultCache:
    """Get or create the global cache instance."""
    global _global_cache

    if _global_cache is None:
        if cache_dir is None:
            cache_dir = Path("output") / ".cache"
        _global_cache = ResultCache(cache_dir=cache_dir)

    return _global_cache


def clear_cache() -> None:
    """Clear the global cache."""
    global _global_cache
    if _global_cache is not None:
        _global_cache.clear()
