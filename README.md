# mcp-docsearch

Semantic search over any markdown corpus, exposed as an [MCP](https://modelcontextprotocol.io) server.

Point it at a directory of markdown. It chunks the files, embeds them into a local
[ChromaDB](https://www.trychroma.com/) vector store, and gives your MCP client — Claude Code,
Claude Desktop, or anything else that speaks MCP — three tools: `search_docs`, `reindex`, and
`index_stats`.

Results come back with **file paths, line numbers, and section breadcrumbs**, so the model can
cite and open the source rather than paraphrasing from a soup of context.

Everything runs locally. No API keys, no documents leaving your machine.

---

## Why

Grep finds the word you typed. It does not find the paragraph that *means* what you meant.

Once a corpus — design docs, a knowledge base, a wiki, a novel — grows past a few dozen files,
an agent needs retrieval, not string matching. This is a small, dependency-light way to give it
one, over a corpus you already have sitting on disk as markdown.

## Install

```bash
git clone https://github.com/MrMattMunro/mcp-docsearch
cd mcp-docsearch
pip install -e .
```

## Quick start

```bash
export DOCSEARCH_CORPUS=/path/to/your/markdown
mcp-docsearch-index          # build the index (first run embeds everything)
```

Then register the server with your MCP client. For Claude Code (`.mcp.json`):

```json
{
  "mcpServers": {
    "docsearch": {
      "command": "mcp-docsearch",
      "env": {
        "DOCSEARCH_CORPUS": "/path/to/your/markdown",
        "DOCSEARCH_COLLECTION": "my_docs"
      }
    }
  }
}
```

Ask your model something like *"search the docs for how authentication is handled"* and it will
call `search_docs` and get back ranked excerpts with line numbers.

## Configuration

All configuration is environment variables, so one install can serve many corpora.

| Variable | Default | Meaning |
|---|---|---|
| `DOCSEARCH_CORPUS` | cwd | Root directory of the markdown corpus |
| `DOCSEARCH_DB` | `<corpus>/.docsearch` | Where the vector store is written |
| `DOCSEARCH_COLLECTION` | `docs` | Collection name (use one per corpus) |
| `DOCSEARCH_CHUNK_MODE` | `auto` | `auto`, `header`, or `window` |
| `DOCSEARCH_WINDOW` | `80` | Lines per window (window mode) |
| `DOCSEARCH_OVERLAP` | `20` | Overlapping lines between windows |
| `DOCSEARCH_EXCLUDE` | — | Extra comma-separated directory names to skip |

## How it works

### Chunking — the part that decides whether retrieval is any good

Chunk badly and no amount of embedding quality will save you: split an idea in half and neither
half retrieves. So there are two strategies, chosen per file.

**`header`** — split on markdown headers, one section per chunk. Right for *structured* docs,
where a section is already a self-contained idea. Each chunk carries its full header chain
(`Guide > Setup > Windows`), which gives the model a breadcrumb for free and makes results
readable at a glance.

**`window`** — fixed-size overlapping line windows. Right for *long-form prose* with few headers
(a novel chapter, a meeting transcript), where header-splitting would yield one giant useless
chunk. Windows overlap so an idea straddling a seam still appears whole in one of them. A runt
tail is absorbed into the previous chunk rather than emitted as a two-line fragment that matches
nothing.

**`auto`** (the default) picks per file: header split if the file has 2+ headers, else windows.

### Incremental indexing

Re-embedding an entire corpus every time you fix a typo is slow and pointless. Each file's mtime
is recorded, so a normal `reindex` only re-embeds files that actually changed. Chunks belonging
to deleted files are removed from the store, so the index can't rot into a graveyard of stale
references.

`reindex(force=True)` does a full rebuild when you want one.

### Retrieval

Cosine similarity over the collection. Results carry `file_path`, `start_line`, `end_line`, and
`header_chain`, and can be filtered by `group` (top-level directory) or `path_prefix`.

## MCP tools

| Tool | Purpose |
|---|---|
| `search_docs(query, n_results, path_prefix, group)` | Ranked excerpts with paths + line numbers |
| `reindex(file_path, force)` | Incremental by default; one file or a full rebuild |
| `index_stats()` | What's indexed, and the active configuration |

## A note on privacy

**The vector store contains embedded copies of your documents.** If your corpus is private, the
index is private too — even if the code around it isn't. `.docsearch/` and `.chromadb/` are in
`.gitignore` for exactly this reason. Don't commit an index.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Licence

MIT
