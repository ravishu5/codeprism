"""Unit tests for CodePrism core models and primitives."""

import pytest
from codeprism.models import (
    ByteSlicedSource,
    Symbol,
    compute_content_hash,
    make_symbol_id,
)


class TestSymbolId:
    def test_basic_symbol_id(self):
        assert (
            make_symbol_id("src/auth.py", "login", "function")
            == "src/auth.py::login#function"
        )

    def test_method_symbol_id(self):
        assert (
            make_symbol_id("src/user.py", "User.get_profile", "method")
            == "src/user.py::User.get_profile#method"
        )

    def test_overload_symbol_id(self):
        assert (
            make_symbol_id("src/api.ts", "fetch_data", "function", overload=1)
            == "src/api.ts::fetch_data~1#function"
        )
        assert (
            make_symbol_id("src/api.ts", "fetch_data", "function", overload=2)
            == "src/api.ts::fetch_data~2#function"
        )

    def test_normalizes_slashes(self):
        assert (
            make_symbol_id(r"src\nested\mod.py", "compute", "function")
            == "src/nested/mod.py::compute#function"
        )
        assert (
            make_symbol_id("/src/root.py", "main", "function")
            == "src/root.py::main#function"
        )


class TestByteSlicedSource:
    def test_ascii_slicing(self):
        raw = b"def add(a, b):\n    return a + b\n"
        source = ByteSlicedSource(raw)
        assert len(source) == len(raw)
        assert source[0:3] == "def"
        assert source[4:7] == "add"
        assert source[19:31] == "return a + b"

    def test_utf8_multi_byte_drift_prevention(self):
        """Verify that emojis and accented UTF-8 characters do NOT cause offset drift.

        In UTF-8:
        - '🔥' is 4 bytes (0xF0 0x9F 0x94 0xA5)
        - 'é' is 2 bytes (0xC3 0xA9)
        """
        # 16 bytes: "# Author: René 🔥\n"
        #   '#' (1) + ' ' (1) + 'Author: ' (8) + 'Ren' (3) + 'é' (2) + ' ' (1) + '🔥' (4) + '\n' (1) = 21 bytes
        header = "# Author: René 🔥\n".encode("utf-8")
        body = "def get_energy():\n    return 100\n".encode("utf-8")
        full_bytes = header + body

        source = ByteSlicedSource(full_bytes)

        # In byte coordinates:
        # body starts at len(header) bytes
        start_byte = len(header)
        end_byte = start_byte + len("def get_energy():")

        # ByteSlicedSource slice
        sliced_func = source[start_byte:end_byte]
        assert sliced_func == "def get_energy():"

        # Contrast with standard Python string slicing using byte indices (which drifts):
        str_text = full_bytes.decode("utf-8")
        corrupted_slice = str_text[start_byte:end_byte]
        # str_text[start_byte] will be off because emojis/accents take fewer characters than bytes!
        assert corrupted_slice != "def get_energy():"
        # This proves the coordinate trap is solved!

    def test_safe_boundary_clipping(self):
        """Ensure slicing midway through a multi-byte UTF-8 char does not raise an unhandled exception."""
        raw = "Hello 🚀 World".encode("utf-8")
        source = ByteSlicedSource(raw)
        # Slicing into the middle of the 4-byte rocket emoji
        partial = source[0:8]
        assert isinstance(partial, str)
        assert partial.startswith("Hello")


class TestSymbolModel:
    def test_symbol_create_and_hashing(self):
        code = b"def calculate_total(items: list) -> float:\n    return sum(items)\n"
        source = ByteSlicedSource(code)

        sym = Symbol.create(
            file_path="src/billing.py",
            name="calculate_total",
            kind="function",
            start_line=1,
            end_line=2,
            start_byte=0,
            end_byte=len(code),
            signature="def calculate_total(items: list) -> float",
            source=source,
            docstring=None,
        )

        assert sym.id == "src/billing.py::calculate_total#function"
        assert sym.name == "calculate_total"
        assert sym.kind == "function"
        assert len(sym.content_hash) == 64  # SHA-256 hex string

        # Changing code changes content_hash
        modified_code = b"def calculate_total(items: list) -> float:\n    return sum(items) * 1.1\n"
        modified_source = ByteSlicedSource(modified_code)

        sym_modified = Symbol.create(
            file_path="src/billing.py",
            name="calculate_total",
            kind="function",
            start_line=1,
            end_line=2,
            start_byte=0,
            end_byte=len(modified_code),
            signature="def calculate_total(items: list) -> float",
            source=modified_source,
        )

        assert sym.id == sym_modified.id  # ID is stable!
        assert sym.content_hash != sym_modified.content_hash  # Hash accurately captures edit!
