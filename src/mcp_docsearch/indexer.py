"""ChromaDB indexing with incremental re-indexing.

Re-embedding an entire corpus on every edit is slow and pointless. We track each
file's mtime, so a normal reindex only touches files that actually changed --
and deletes chunks for files that have vanished.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import chromadb

from .chunking import Chunk, chunk_lines
from .config import Config, load_config


def get_collection(cfg: Config):
    """Get or create the ChromaDB collection (cosine distance)."""
    cfg.db_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(cfg.db_path))
    return client.get_or_create_collection(
        name=cfg.collection,
        metadata={"hnsw:space": "cosine"},
    )


def discover_files(cfg: Config) -> list[tuple[Path, str]]:
    """Return (abs_path, rel_path) for every indexable markdown file."""
    found: list[tuple[Path, str]] = []
    for abs_path in sorted(cfg.corpus.rglob("*.md")):
        if not abs_path.is_file():
            continue
        rel = abs_path.relative_to(cfg.corpus)
        if any(part in cfg.excludes for part in rel.parts):
            continue
        found.append((abs_path, rel.as_posix()))
    return found


def group_of(rel_path: str) -> str:
    """Top-level directory under the corpus root -- a free, generic facet to filter on."""
    parts = rel_path.split("/")
    return parts[0] if len(parts) > 1 else ""


def chunk_file(abs_path: Path, rel_path: str, cfg: Config) -> list[Chunk]:
    lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return chunk_lines(
        lines,
        rel_path,
        group_of(rel_path),
        mode=cfg.chunk_mode,
        window=cfg.window,
        overlap=cfg.overlap,
    )


def load_mtimes(cfg: Config) -> dict[str, float]:
    if cfg.mtime_file.exists():
        try:
            return json.loads(cfg.mtime_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_mtimes(cfg: Config, mtimes: dict[str, float]) -> None:
    cfg.mtime_file.parent.mkdir(parents=True, exist_ok=True)
    cfg.mtime_file.write_text(json.dumps(mtimes, indent=2), encoding="utf-8")


def drop_file(collection, rel_path: str) -> int:
    """Remove every chunk belonging to one file. Returns how many were removed."""
    existing = collection.get(where={"file_path": rel_path})
    ids = existing.get("ids") or []
    if ids:
        collection.delete(ids=ids)
    return len(ids)


def index_file(abs_path: Path, rel_path: str, collection, cfg: Config) -> int:
    """Replace a file's chunks in the index. Returns the new chunk count."""
    drop_file(collection, rel_path)

    chunks = chunk_file(abs_path, rel_path, cfg)
    if not chunks:
        return 0

    collection.add(
        ids=[c.chunk_id for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[
            {
                "file_path": c.file_path,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "header_chain": c.header_chain,
                "group": c.group,
            }
            for c in chunks
        ],
    )
    return len(chunks)


def build_index(cfg: Config | None = None, force: bool = False) -> dict:
    """Index the corpus. Incremental unless force=True.

    Returns {rel_path: chunk_count | "deleted (n chunks)", ..., "_total": int}.
    """
    cfg = cfg or load_config()
    collection = get_collection(cfg)

    previous = {} if force else load_mtimes(cfg)
    current: dict[str, float] = {}
    stats: dict[str, object] = {}

    for abs_path, rel_path in discover_files(cfg):
        mtime = abs_path.stat().st_mtime
        current[rel_path] = mtime

        if not force and previous.get(rel_path) == mtime:
            continue  # untouched since last run

        stats[rel_path] = index_file(abs_path, rel_path, collection, cfg)

    # Files that disappeared since the last index must not linger in the store.
    for gone in set(previous) - set(current):
        removed = drop_file(collection, gone)
        if removed:
            stats[gone] = f"deleted ({removed} chunks)"

    save_mtimes(cfg, current)
    stats["_total"] = collection.count()
    return stats


def reindex_one(rel_path: str, cfg: Config | None = None) -> dict:
    """Re-index a single file by its corpus-relative path."""
    cfg = cfg or load_config()
    abs_path = cfg.corpus / rel_path
    if not abs_path.exists():
        return {"error": f"File not found: {rel_path}"}

    collection = get_collection(cfg)
    count = index_file(abs_path, Path(rel_path).as_posix(), collection, cfg)

    mtimes = load_mtimes(cfg)
    mtimes[Path(rel_path).as_posix()] = abs_path.stat().st_mtime
    save_mtimes(cfg, mtimes)

    return {rel_path: count, "_total": collection.count()}


def main() -> None:
    """CLI: build the index up front, so the first search isn't a cold start."""
    force = "--force" in sys.argv
    cfg = load_config()

    print(f"Corpus:     {cfg.corpus}")
    print(f"Store:      {cfg.db_path}")
    print(f"Collection: {cfg.collection}")
    print(f"Chunking:   {cfg.chunk_mode}")
    print(f"Indexing{' (full rebuild)' if force else ' (incremental)'}...\n")

    stats = build_index(cfg, force=force)
    total = stats.pop("_total")

    if not stats:
        print("Already up to date.")
    else:
        for path, count in sorted(stats.items()):
            print(f"  {path}: {count}")

    print(f"\nTotal chunks: {total}")


if __name__ == "__main__":
    main()
