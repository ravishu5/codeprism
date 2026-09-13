# Phase 1: Foundation & Data Models Guide

> **Project:** `CodePrism`
> **Status:** ✅ Completed & Verified
> **Core Files:** [`src/codeprism/models.py`](file:///Users/ravi/Desktop/learn_with_gemini/codeprism/src/codeprism/models.py) and [`tests/test_models.py`](file:///Users/ravi/Desktop/learn_with_gemini/codeprism/tests/test_models.py)

---

## 1. Why We Need This Layer

Before we can parse ASTs or store code in databases, we need answers to two fundamental questions:
1. **How do we identify a code element across time and edits?**
2. **How do we extract a slice of code without corrupting it?**

If these two foundations are flawed, every downstream component (retrieval, diffing, call graphs) breaks.

---

## 2. Concept 1: Stable Symbol IDs

### The Line Number Trap
In simple scripts, tools often reference code by line numbers: `src/auth.py:45`.
**Why this fails:** If a developer adds a 2-line comment at the top of the file, every single line number shifts. All cached references, call graphs, and bookmarks immediately break.

### The Canonical Symbol ID Specification
A symbol must have an identity derived from its **hierarchical name and kind**, not its line number:

$$\text{Symbol ID} = \texttt{\{file\_path\}::\{qualified\_name\}\#\{kind\}}$$

#### Format Rules:
* `file_path`: Relative path from the repository root (e.g. `src/auth.py`), normalized to forward slashes.
* `qualified_name`: The hierarchical path to the symbol:
  * Top-level function: `login`
  * Class: `User`
  * Method inside class: `User.login`
  * Nested method: `Outer.Inner.method`
* `kind`: Lowercase category: `function`, `class`, `method`, `constant`, `type`.
* **Overload Disambiguation:** In languages supporting method overloads (TypeScript, Python `@overload`, C++, Java), if two symbols in the same scope share the exact name and kind, append a numeric suffix: `~1`, `~2`.
  * First occurrence: `src/api.py::get_user#function`
  * Second occurrence: `src/api.py::get_user~1#function`

---

## 3. Concept 2: The UTF-8 Byte Offset Coordinate Problem

This is one of the most critical gotchas in building Tree-sitter-based tools.

### The Coordinate Mismatch
* **Tree-sitter** is written in C and measures syntax node boundaries in **UTF-8 byte offsets** (`node.start_byte`, `node.end_byte`).
* **Python's `str`** is indexed by **Unicode code points (characters)**, not bytes.

### Why Slicing a Python String Corrupts Code:
Consider a file with non-ASCII characters (emojis, accented characters, localized text):
```python
# Author: René Müller 🚀
def hello():
    return "world"
```
1. In UTF-8 bytes:
   - `é` is 2 bytes (`0xC3 0xA9`).
   - `ü` is 2 bytes (`0xC3 0xBC`).
   - `🚀` is 4 bytes (`0xF0 0x9F 0x9A 0x80`).
2. Tree-sitter calculates `hello` starting at byte offset `34`.
3. But in Python string characters, `hello` starts at character index `29`!
4. If you execute:
   ```python
   source_str[start_byte:end_byte]
   ```
   Python slices using *character indices*. The slice starts 5 characters too late, returning mangled code! Because identifiers usually retain their length, the corrupt slice often looks like plausible code rather than an obvious crash, causing silent hallucinations.

### The Solution: `ByteSlicedSource`
We created a custom wrapper around raw file `bytes`:
```python
class ByteSlicedSource:
    def __init__(self, data: bytes | str) -> None:
        self._data = data if isinstance(data, bytes) else data.encode("utf-8")

    def __getitem__(self, key: slice | int) -> str:
        # Slices directly in byte-space, then decodes to UTF-8
        chunk = self._data[key] if isinstance(key, slice) else self._data[key:key + 1]
        try:
            return chunk.decode("utf-8")
        except UnicodeDecodeError as exc:
            # Handle boundary clips gracefully
            if exc.end == len(chunk) and exc.start >= len(chunk) - 3:
                try:
                    return chunk[: exc.start].decode("utf-8")
                except UnicodeDecodeError:
                    pass
            return chunk.decode("utf-8", errors="replace")
```
Now, `source[node.start_byte : node.end_byte]` operates in the **exact coordinate system** of Tree-sitter.

---

## 4. Completed Implementation Reference

The implemented module [`src/codeprism/models.py`](file:///Users/ravi/Desktop/learn_with_gemini/codeprism/src/codeprism/models.py) exposes:

### `make_symbol_id`
```python
def make_symbol_id(
    file_path: str,
    qualified_name: str,
    kind: str,
    overload: int = 0,
) -> str:
    clean_path = file_path.replace("\\", "/").lstrip("/")
    overload_suffix = f"~{overload}" if overload > 0 else ""
    return f"{clean_path}::{qualified_name}{overload_suffix}#{kind.lower()}"
```

### `compute_content_hash`
Computes a SHA-256 hex digest of the raw byte slice:
```python
def compute_content_hash(content: Union[bytes, str]) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()
```

### `Symbol` Model
A frozen Pydantic model representing a fully resolved code symbol:
```python
class Symbol(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    kind: str
    file_path: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    signature: str
    docstring: Optional[str] = None
    parent: Optional[str] = None
    content_hash: str
```
It includes a factory constructor `Symbol.create(...)` which automatically slices raw source bytes, calculates the SHA-256 hash, and generates the canonical ID in one call.

---

## 5. Verification Suite & Test Results

The test suite in [`tests/test_models.py`](file:///Users/ravi/Desktop/learn_with_gemini/codeprism/tests/test_models.py) covers:

1. **`test_basic_symbol_id` & `test_method_symbol_id`**: Verifies deterministic `{path}::{name}#{kind}` formatting.
2. **`test_overload_symbol_id`**: Verifies `~1`, `~2` overload suffixes for TypeScript / Python function overloading.
3. **`test_normalizes_slashes`**: Verifies Windows backslashes `\` and leading slashes are normalized.
4. **`test_ascii_slicing`**: Verifies direct byte-level string extraction.
5. **`test_utf8_multi_byte_drift_prevention`**: 
   - Uses a file header with emojis (`🔥`) and accented characters (`é`).
   - Slices using exact Tree-sitter byte offsets.
   - Proves `ByteSlicedSource` extracts `"def get_energy():"` cleanly, whereas naive Python `str[start:end]` drifts and extracts corrupt text.
6. **`test_safe_boundary_clipping`**: Verifies slicing midway through a multi-byte boundary falls back cleanly without crashing.
7. **`test_symbol_create_and_hashing`**: Verifies that editing code changes `content_hash` while preserving stable `id`.

### Test Run Output:
```text
============================== test session starts ==============================
rootdir: /Users/ravi/Desktop/learn_with_gemini/codeprism
configfile: pyproject.toml
testpaths: tests
collected 8 items

tests/test_models.py ........                                            [100%]
============================== 8 passed in 0.05s ===============================
```
