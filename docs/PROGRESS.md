# CodePrism Implementation Tracker

Track progress across all milestones as we implement **CodePrism**.

- [x] **Phase 1: Foundation & Data Models**
  - [x] Add dependencies (`tree-sitter-language-pack`, `pydantic`, `mcp`, `httpx`, `pytest`)
  - [x] Create `src/codeprism/models.py`
    - [x] `make_symbol_id(file_path, qualified_name, kind, overload=0)`
    - [x] `ByteSlicedSource` with UTF-8 byte-offset handling
    - [x] `Symbol` model definition (with SHA-256 `content_hash`)
  - [x] Create and pass `tests/test_models.py` (8 passed in 0.05s)

- [ ] **Phase 2: Tree-Sitter AST Parsing & Symbol Extractor**
  - [ ] Language specification registry (`LanguageSpec`)
  - [ ] Multi-language AST walker
  - [ ] Docstring and signature extraction
  - [ ] Overload disambiguation pass (`~1`, `~2`)
  - [ ] Unit tests for multi-language extraction (Python, JS/TS, Go)

- [ ] **Phase 3: SQLite WAL Storage & Indexing Engine**
  - [ ] SQLite database schema (`symbols`, `files`, `imports`, `raw_cache`)
  - [ ] WAL mode configuration & single-writer concurrent readers
  - [ ] Fast byte-seeking file cache
  - [ ] Incremental indexing & mtime/SHA-256 change detection

- [ ] **Phase 4: Import Graph & Code Intelligence**
  - [ ] Import specifier resolver
  - [ ] PageRank centrality calculation over file graph
  - [ ] AST-derived Call Hierarchy (callers/callees)
  - [ ] Blast Radius calculation

- [ ] **Phase 5: Hybrid Search & Signal Fusion Engine**
  - [ ] Inverted index & BM25 ranking
  - [ ] Query Shape extraction (pinning exact identifier tokens)
  - [ ] Weighted Reciprocal Rank (WRR) fusion
  - [ ] Calibrated confidence scoring (gap, strength, identity, freshness)

- [ ] **Phase 6: The 3-Verb Front Door & MCP Server**
  - [ ] FastMCP server lifecycle
  - [ ] Front Door tools: `route`, `menu`, `order`
  - [ ] Guardrails (`allow_state_change`, forbidden execution tripwires)
  - [ ] Live token savings meter & `_meta` response envelope

- [ ] **Phase 7: Production Hardening & PreToolUse Hooks**
  - [ ] PreToolUse steering hook (redirecting `Read`, `Grep`, `Glob`)
  - [ ] Watchfiles background auto-reindexing
  - [ ] Ratchet tests & CI gates
