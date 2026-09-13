# Phase 1: Foundation & Data Models Guide

> **Project:** `CodePrism`
> **Goal:** Build the core primitives for symbol identity, source representation, and coordinate handling.
> **Files to create:** `src/codeprism/models.py` and `tests/test_models.py`

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
* `file_path`: Relative path from the repository root (e.g. `src/auth.py`).
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
We create a custom class wrapping the raw file `bytes`:
```python
class ByteSlicedSource:
    def __init__(self, data: bytes):
        self._data = data

    def __getitem__(self, key: slice | int) -> str:
        # Slices directly in byte-space, then decodes to UTF-8
        chunk = self._data[key] if isinstance(key, slice) else self._data[key:key + 1]
        return chunk.decode("utf-8", errors="replace")
```
Now, `source[node.start_byte : node.end_byte]` operates in the **exact coordinate system** of Tree-sitter.

---

## 4. Specification: Data Structures to Implement

### `src/codeprism/models.py`

You will implement the following:

#### 1. Helper: `make_symbol_id`
```python
def make_symbol_id(file_path: str, qualified_name: str, kind: str, overload: int = 0) -> str:
    """Generate a canonical symbol ID string.
    
    Examples:
        make_symbol_id("src/auth.py", "login", "function") 
        -> "src/auth.py::login#function"
        
        make_symbol_id("src/auth.py", "login", "function", overload=1) 
        -> "src/auth.py::login~1#function"
    """
```

#### 2. Class: `ByteSlicedSource`
* Holds raw `bytes`.
* `__len__`: Returns length in bytes.
* `__getitem__(self, key: slice | int) -> str`: Returns decoded string slice.
* Handles safe UTF-8 decoding (fallback gracefully if a slice clips a multi-byte boundary).

#### 3. Class: `Symbol` (Dataclass or Pydantic)
* `id: str` (Canonical ID)
* `name: str` (Bare identifier, e.g. `"login"`)
* `kind: str` (`"function"`, `"class"`, `"method"`, `"constant"`, `"type"`)
* `file_path: str` (Repo-relative path)
* `start_line: int` (1-indexed start line)
* `end_line: int` (1-indexed end line)
* `start_byte: int` (Byte offset into file)
* `end_byte: int` (Byte offset into file)
* `signature: str` (Signature or declaration head, e.g. `def login(username: str) -> bool`)
* `docstring: Optional[str] = None`
* `parent: Optional[str] = None` (Parent class or namespace if nested)
* `content_hash: str` (SHA-256 hex digest of the symbol's exact raw byte slice)

---

## 5. Verification: What Tests Must Pass

Create `tests/test_models.py` with tests verifying:
1. `test_symbol_id_generation`: Correct formatting for regular and overloaded symbols.
2. `test_byte_sliced_source_ascii`: Standard ASCII string slicing.
3. `test_byte_sliced_source_utf8_offset`: Verify that a file containing multi-byte UTF-8 (emojis/non-ASCII) does **not** experience coordinate drift when sliced with byte offsets.
4. `test_symbol_content_hash`: Verify that SHA-256 content hashing accurately flags changes in code content.
