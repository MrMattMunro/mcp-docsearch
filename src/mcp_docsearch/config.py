"""Configuration, resolved from environment variables.

Everything is overridable so the server can point at any markdown corpus without
code changes -- that is the whole point of this package.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_EXCLUDES = (
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".chromadb",
    ".docsearch",
)


def _env_path(name: str, default: Path | None = None) -> Path | None:
    raw = os.environ.get(name)
    if not raw:
        return default
    return Path(raw).expanduser().resolve()


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    """Resolved runtime configuration."""

    corpus: Path
    db_path: Path
    collection: str
    chunk_mode: str          # "auto" | "header" | "window"
    window: int              # lines per window (window mode)
    overlap: int             # overlapping lines between windows
    excludes: tuple[str, ...] = field(default=DEFAULT_EXCLUDES)

    @property
    def mtime_file(self) -> Path:
        return self.db_path / "file_mtimes.json"


def load_config() -> Config:
    """Build Config from the environment.

    DOCSEARCH_CORPUS      Root directory of the markdown corpus (default: cwd)
    DOCSEARCH_DB          Where the vector store lives (default: <corpus>/.docsearch)
    DOCSEARCH_COLLECTION  Collection name (default: "docs")
    DOCSEARCH_CHUNK_MODE  auto | header | window   (default: auto)
    DOCSEARCH_WINDOW      Lines per window in window mode (default: 80)
    DOCSEARCH_OVERLAP     Overlap between windows (default: 20)
    DOCSEARCH_EXCLUDE     Comma-separated extra directory names to skip
    """
    corpus = _env_path("DOCSEARCH_CORPUS", Path.cwd()) or Path.cwd()
    db_path = _env_path("DOCSEARCH_DB", corpus / ".docsearch")

    chunk_mode = os.environ.get("DOCSEARCH_CHUNK_MODE", "auto").strip().lower()
    if chunk_mode not in {"auto", "header", "window"}:
        chunk_mode = "auto"

    extra = os.environ.get("DOCSEARCH_EXCLUDE", "")
    excludes = DEFAULT_EXCLUDES + tuple(
        p.strip() for p in extra.split(",") if p.strip()
    )

    window = _env_int("DOCSEARCH_WINDOW", 80)
    overlap = _env_int("DOCSEARCH_OVERLAP", 20)
    if overlap >= window:  # a non-advancing stride would loop forever
        overlap = max(0, window // 4)

    return Config(
        corpus=corpus,
        db_path=db_path,  # type: ignore[arg-type]
        collection=os.environ.get("DOCSEARCH_COLLECTION", "docs").strip() or "docs",
        chunk_mode=chunk_mode,
        window=window,
        overlap=overlap,
        excludes=excludes,
    )
