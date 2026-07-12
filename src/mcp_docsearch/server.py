"""MCP server exposing semantic search over a markdown corpus."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .indexer import build_index, get_collection, reindex_one

mcp = FastMCP("docsearch")

MAX_EXCERPT_CHARS = 1500
MAX_RESULTS = 20


@mcp.tool()
def search_docs(
    query: str,
    n_results: int = 5,
    path_prefix: str = "",
    group: str = "",
) -> str:
    """Semantic search over the indexed markdown corpus.

    Returns ranked excerpts with file paths, line numbers and section breadcrumbs,
    so the caller can open the source directly.

    Args:
        query: Natural-language query (e.g. "how does incremental indexing work").
        n_results: Number of results, 1-20 (default 5).
        path_prefix: Only match files whose path starts with this (e.g. "guides/").
        group: Only match files in this top-level directory.
    """
    cfg = load_config()
    collection = get_collection(cfg)

    if collection.count() == 0:
        return "Index is empty. Run `mcp-docsearch-index` or call reindex(force=True)."

    where = {"group": group} if group else None

    results = collection.query(
        query_texts=[query],
        n_results=max(1, min(MAX_RESULTS, n_results)),
        **({"where": where} if where else {}),
    )

    ids = results["ids"][0] if results["ids"] else []
    if not ids:
        return "No results found."

    blocks: list[str] = []
    for rank, (doc, meta, dist) in enumerate(
        zip(results["documents"][0], results["metadatas"][0], results["distances"][0]),
        start=1,
    ):
        path = str(meta.get("file_path", ""))
        if path_prefix and not path.startswith(path_prefix):
            continue

        text = doc if len(doc) <= MAX_EXCERPT_CHARS else doc[:MAX_EXCERPT_CHARS] + "..."
        score = 1 - dist  # cosine distance -> similarity
        header = meta.get("header_chain") or ""
        section = f"\nSection: {header}" if header else ""

        blocks.append(
            f"[{rank}] {path} "
            f"(lines {meta.get('start_line')}-{meta.get('end_line')}) "
            f"[score: {score:.2f}]{section}\n---\n{text}"
        )

    if not blocks:
        return "No results found (all matches filtered out by path_prefix)."

    return "\n\n".join(blocks)


@mcp.tool()
def reindex(file_path: str = "", force: bool = False) -> str:
    """Rebuild the search index.

    Incremental by default -- only files whose mtime changed are re-embedded.

    Args:
        file_path: Re-index just this one file (corpus-relative path).
        force: Full rebuild, ignoring mtimes. Ignored when file_path is set.
    """
    if file_path:
        stats = reindex_one(file_path)
        if "error" in stats:
            return str(stats["error"])
        total = stats.pop("_total")
        lines = [f"Re-indexed {path}: {count} chunks" for path, count in stats.items()]
        lines.append(f"Total chunks: {total}")
        return "\n".join(lines)

    stats = build_index(force=force)
    total = stats.pop("_total")

    if not stats:
        return f"Index already up to date. Total chunks: {total}"

    lines = [f"  {path}: {count}" for path, count in sorted(stats.items())]
    action = "Rebuilt" if force else "Updated"
    return f"{action} index:\n" + "\n".join(lines) + f"\n\nTotal chunks: {total}"


@mcp.tool()
def index_stats() -> str:
    """Report what is currently indexed and how the server is configured."""
    cfg = load_config()
    collection = get_collection(cfg)
    return (
        f"Corpus:     {cfg.corpus}\n"
        f"Store:      {cfg.db_path}\n"
        f"Collection: {cfg.collection}\n"
        f"Chunking:   {cfg.chunk_mode} (window={cfg.window}, overlap={cfg.overlap})\n"
        f"Chunks:     {collection.count()}"
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
