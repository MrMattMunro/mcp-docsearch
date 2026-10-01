# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Continuous integration: the test suite runs on Python 3.10–3.13.

## [0.1.0] - 2026-07-12

### Added
- Initial release.
- MCP server exposing `search_docs`, `reindex`, and `index_stats` over a local
  markdown corpus.
- Two chunking strategies — `header` (one section per chunk, with a header-chain
  breadcrumb) and `window` (overlapping fixed-size windows for long-form prose) —
  with an `auto` mode that picks per file.
- Incremental indexing keyed on file mtime, with removal of chunks for deleted
  files; `reindex(force=True)` for a full rebuild.
- Local ChromaDB vector store with cosine similarity. No API keys; nothing leaves
  the machine.
- Per-corpus configuration via environment variables, so one install can serve
  several independent collections.

[Unreleased]: https://github.com/MrMattMunro/mcp-docsearch/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/MrMattMunro/mcp-docsearch/releases/tag/v0.1.0
