"""Markdown-aware chunking.

Two strategies, because one size does not fit all prose:

* **header** -- split on markdown headers, one section per chunk. Ideal for
  structured reference docs, where a section is a self-contained idea and the
  header chain ("Guide > Setup > Windows") is a useful breadcrumb for the model.

* **window** -- fixed-size overlapping line windows. Ideal for long-form prose
  with few headers (a novel chapter, a transcript), where header splitting would
  produce one enormous chunk. Overlap prevents an idea being severed at a seam.

"auto" picks per-file: header split when the file has >= 2 headers, else window.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HEADER_RE = re.compile(r"^(#{1,4})\s+(.+)$")
H1_RE = re.compile(r"^#\s+(.+)$")

# A trailing window shorter than this (in non-blank lines) is absorbed into the
# previous chunk rather than emitted as a runt.
MIN_TAIL_LINES = 5


@dataclass
class Chunk:
    chunk_id: str      # "{rel_path}::{start_line}-{end_line}"
    file_path: str     # relative to corpus root, forward slashes
    start_line: int    # 1-indexed
    end_line: int      # 1-indexed, inclusive
    header_chain: str  # "Doc Title > Section > Subsection"
    group: str         # top-level directory under the corpus root ("" if at root)
    text: str


def count_headers(lines: list[str]) -> int:
    return sum(1 for line in lines if HEADER_RE.match(line))


def chunk_by_header(lines: list[str], rel_path: str, group: str) -> list[Chunk]:
    """One chunk per markdown section, carrying its full header breadcrumb."""
    chunks: list[Chunk] = []
    header_stack: dict[int, str] = {}
    block_start = 1
    block_lines: list[str] = []

    def emit(end_line: int) -> None:
        text = "\n".join(block_lines).strip()
        if not text:
            return
        chain = [header_stack[d] for d in sorted(header_stack)]
        chunks.append(
            Chunk(
                chunk_id=f"{rel_path}::{block_start}-{end_line}",
                file_path=rel_path,
                start_line=block_start,
                end_line=end_line,
                header_chain=" > ".join(chain),
                group=group,
                text=text,
            )
        )

    for i, line in enumerate(lines, start=1):
        m = HEADER_RE.match(line)
        if not m:
            block_lines.append(line)
            continue

        if block_lines:
            emit(i - 1)

        depth = len(m.group(1))
        header_stack[depth] = m.group(2).strip()
        # A shallower header invalidates everything nested beneath it.
        for d in [d for d in header_stack if d > depth]:
            del header_stack[d]

        block_start = i
        block_lines = [line]

    if block_lines:
        emit(len(lines))

    return chunks


def chunk_by_window(
    lines: list[str],
    rel_path: str,
    group: str,
    window: int = 80,
    overlap: int = 20,
) -> list[Chunk]:
    """Overlapping fixed-size windows, tagged with the nearest preceding H1."""
    chunks: list[Chunk] = []
    total = len(lines)
    if total == 0:
        return chunks

    stride = max(1, window - overlap)

    h1s: list[tuple[int, str]] = [
        (i, m.group(1).strip())
        for i, line in enumerate(lines)
        if (m := H1_RE.match(line))
    ]

    def nearest_h1(idx: int) -> str:
        title = ""
        for pos, text in h1s:
            if pos > idx:
                break
            title = text
        return title

    pos = 0
    while pos < total:
        end = min(pos + window, total)

        # Absorb a runt tail rather than emitting a near-empty final chunk.
        tail = lines[end:]
        if tail and sum(1 for line in tail if line.strip()) < MIN_TAIL_LINES:
            end = total

        text = "\n".join(lines[pos:end]).strip()
        if text:
            chunks.append(
                Chunk(
                    chunk_id=f"{rel_path}::{pos + 1}-{end}",
                    file_path=rel_path,
                    start_line=pos + 1,
                    end_line=end,
                    header_chain=nearest_h1(pos),
                    group=group,
                    text=text,
                )
            )

        if end >= total:
            break
        pos += stride

    return chunks


def chunk_lines(
    lines: list[str],
    rel_path: str,
    group: str,
    mode: str = "auto",
    window: int = 80,
    overlap: int = 20,
) -> list[Chunk]:
    """Chunk one file's lines using the configured strategy."""
    if mode == "auto":
        mode = "header" if count_headers(lines) >= 2 else "window"

    if mode == "header":
        return chunk_by_header(lines, rel_path, group)
    return chunk_by_window(lines, rel_path, group, window=window, overlap=overlap)
