"""Chunking is the part that decides whether retrieval is any good, so it's the part with tests."""

from mcp_docsearch.chunking import (
    chunk_by_header,
    chunk_by_window,
    chunk_lines,
    count_headers,
)

DOC = """# Guide

Intro line.

## Setup

Install it.

### Windows

Use the installer.

## Usage

Run it.
""".splitlines()


def test_header_split_produces_one_chunk_per_section():
    chunks = chunk_by_header(DOC, "guide.md", "")
    assert [c.header_chain for c in chunks] == [
        "Guide",
        "Guide > Setup",
        "Guide > Setup > Windows",
        "Guide > Usage",
    ]


def test_header_chain_pops_deeper_levels():
    """A later H2 must not inherit the previous H3 breadcrumb."""
    chunks = chunk_by_header(DOC, "guide.md", "")
    usage = next(c for c in chunks if c.text.startswith("## Usage"))
    assert usage.header_chain == "Guide > Usage"


def test_line_numbers_are_1_indexed_and_inclusive():
    chunks = chunk_by_header(DOC, "guide.md", "")
    assert chunks[0].start_line == 1
    # Sections must tile the document without gaps or overlaps.
    for prev, nxt in zip(chunks, chunks[1:]):
        assert nxt.start_line == prev.end_line + 1


def test_window_split_overlaps():
    lines = [f"line {i}" for i in range(1, 101)]
    chunks = chunk_by_window(lines, "prose.md", "", window=40, overlap=10)
    assert len(chunks) > 1
    # Consecutive windows must share `overlap` lines, or an idea could be cut in half.
    assert chunks[1].start_line == chunks[0].start_line + 30


def test_window_split_absorbs_runt_tail():
    """A 2-line remainder should be absorbed, not emitted as its own chunk."""
    lines = [f"line {i}" for i in range(1, 43)]
    chunks = chunk_by_window(lines, "prose.md", "", window=40, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].end_line == 42


def test_window_split_terminates_when_overlap_would_stall():
    # stride would be 0; must not spin forever.
    lines = [f"line {i}" for i in range(1, 30)]
    chunks = chunk_by_window(lines, "prose.md", "", window=10, overlap=10)
    assert chunks


def test_auto_mode_uses_windows_for_headerless_prose():
    prose = ["Once upon a time."] * 200
    chunks = chunk_lines(prose, "novel.md", "", mode="auto", window=80, overlap=20)
    assert len(chunks) > 1
    assert all(c.header_chain == "" for c in chunks)


def test_auto_mode_uses_headers_when_present():
    chunks = chunk_lines(DOC, "guide.md", "", mode="auto")
    assert count_headers(DOC) >= 2
    assert chunks[0].header_chain == "Guide"


def test_chunk_ids_are_unique_and_stable():
    chunks = chunk_lines(DOC, "guide.md", "", mode="header")
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert chunks[0].chunk_id.startswith("guide.md::")


def test_empty_file_yields_no_chunks():
    assert chunk_lines([], "empty.md", "", mode="auto") == []
