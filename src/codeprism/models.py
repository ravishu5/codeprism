"""Core data models and primitives for CodePrism.

Defines the fundamental structures for:
- Stable Symbol IDs (hierarchical, line-independent identity)
- ByteSlicedSource (coordinate-safe UTF-8 byte-offset slicing)
- Symbol model (metadata, byte coordinates, and content hashing)
"""

from __future__ import annotations

import hashlib
from typing import Optional, Union
from pydantic import BaseModel, Field, ConfigDict


def make_symbol_id(
    file_path: str,
    qualified_name: str,
    kind: str,
    overload: int = 0,
) -> str:
    """Generate a stable, canonical symbol ID string.

    Format:
        {file_path}::{qualified_name}{~overload if overload > 0}#{kind}

    Examples:
        >>> make_symbol_id("src/auth.py", "User.login", "method")
        'src/auth.py::User.login#method'
        >>> make_symbol_id("src/api.py", "get_user", "function", overload=1)
        'src/api.py::get_user~1#function'
    """
    clean_path = file_path.replace("\\", "/").lstrip("/")
    overload_suffix = f"~{overload}" if overload > 0 else ""
    return f"{clean_path}::{qualified_name}{overload_suffix}#{kind.lower()}"


def compute_content_hash(content: Union[bytes, str]) -> str:
    """Compute SHA-256 hex digest of raw code content."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


class ByteSlicedSource:
    """A text view indexed by BYTE offsets, not character offsets.

    Tree-sitter produces syntax tree nodes with `node.start_byte` and
    `node.end_byte`. In Python, `str` indexing operates on Unicode codepoints
    (characters). When files contain multi-byte UTF-8 sequences (emojis,
    accented characters, non-ASCII comments), character index drifts from
    byte offset, causing string slicing to extract corrupt code.

    ByteSlicedSource slices directly on the underlying `bytes` in byte-space,
    then decodes the resulting chunk into text.
    """

    __slots__ = ("_data",)

    def __init__(self, data: Union[bytes, str]) -> None:
        if isinstance(data, str):
            self._data = data.encode("utf-8")
        else:
            self._data = bytes(data)

    def __getitem__(self, key: Union[slice, int]) -> str:
        if isinstance(key, slice):
            chunk = self._data[key]
        else:
            chunk = self._data[key : key + 1]

        try:
            return chunk.decode("utf-8")
        except UnicodeDecodeError as exc:
            # Handle slices that clip across multi-byte UTF-8 boundaries at the edge
            if exc.end == len(chunk) and exc.start >= len(chunk) - 3:
                try:
                    return chunk[: exc.start].decode("utf-8")
                except UnicodeDecodeError:
                    pass
            return chunk.decode("utf-8", errors="replace")

    def __len__(self) -> int:
        """Return the length of the source in raw bytes."""
        return len(self._data)

    def __str__(self) -> str:
        """Decode the entire source into text."""
        return self._data.decode("utf-8", errors="replace")

    @property
    def raw_bytes(self) -> bytes:
        """Access the underlying immutable bytes."""
        return self._data


class Symbol(BaseModel):
    """Normalized symbol representation in CodePrism."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Canonical symbol ID: {file}::{name}#{kind}")
    name: str = Field(description="Bare identifier name, e.g. login")
    kind: str = Field(description="Symbol category: function, class, method, constant, type")
    file_path: str = Field(description="Repo-relative file path, e.g. src/auth.py")
    start_line: int = Field(description="1-indexed starting line")
    end_line: int = Field(description="1-indexed ending line")
    start_byte: int = Field(description="0-indexed start byte offset into the file")
    end_byte: int = Field(description="0-indexed end byte offset into the file")
    signature: str = Field(description="Function/method signature or declaration header")
    docstring: Optional[str] = Field(default=None, description="Extracted docstring/comment")
    parent: Optional[str] = Field(default=None, description="Parent qualified name (e.g. class name)")
    content_hash: str = Field(description="SHA-256 hash of the symbol's exact raw byte slice")

    @classmethod
    def create(
        cls,
        file_path: str,
        name: str,
        kind: str,
        start_line: int,
        end_line: int,
        start_byte: int,
        end_byte: int,
        signature: str,
        source: Union[bytes, ByteSlicedSource],
        parent: Optional[str] = None,
        docstring: Optional[str] = None,
        overload: int = 0,
    ) -> Symbol:
        """Convenience constructor that calculates canonical ID and content hash."""
        qualified_name = f"{parent}.{name}" if parent else name
        sym_id = make_symbol_id(file_path, qualified_name, kind, overload=overload)

        if isinstance(source, ByteSlicedSource):
            raw_slice = source.raw_bytes[start_byte:end_byte]
        else:
            raw_slice = source[start_byte:end_byte]

        c_hash = compute_content_hash(raw_slice)

        return cls(
            id=sym_id,
            name=name,
            kind=kind,
            file_path=file_path.replace("\\", "/").lstrip("/"),
            start_line=start_line,
            end_line=end_line,
            start_byte=start_byte,
            end_byte=end_byte,
            signature=signature,
            docstring=docstring,
            parent=parent,
            content_hash=c_hash,
        )


__all__ = [
    "make_symbol_id",
    "compute_content_hash",
    "ByteSlicedSource",
    "Symbol",
]
