"""Read a GGUF header without loading the model.

The plan (§5) is explicit: a wrong or missing filename is a startup error, not a fallback to another
quantization. Checking the header is the cheapest way to honour that — magic, version, architecture,
quantization label — and it costs one seek per key instead of 5 GB of VRAM.
"""

from __future__ import annotations

import struct
from pathlib import Path

MAGIC = b"GGUF"
_STRLEN = struct.Struct("<Q")
_U32 = struct.Struct("<I")

#: GGUF metadata value types (spec v3).
_SCALARS = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f",
            7: "<?", 10: "<Q", 11: "<q", 12: "<d"}


class GGUFError(RuntimeError):
    pass


def _read_string(fh) -> str:
    n = _STRLEN.unpack(fh.read(8))[0]
    return fh.read(n).decode("utf-8", "replace")


def _read_value(fh, kind: int):
    if kind in _SCALARS:
        fmt = _SCALARS[kind]
        return struct.unpack(fmt, fh.read(struct.calcsize(fmt)))[0]
    if kind == 8:
        return _read_string(fh)
    if kind == 9:
        elem = _U32.unpack(fh.read(4))[0]
        count = _STRLEN.unpack(fh.read(8))[0]
        values = [_read_value(fh, elem) for _ in range(count)]
        return values[:4] + (["…"] if count > 4 else [])
    raise GGUFError(f"unknown metadata value type {kind}")


def read_header(path: str | Path, keys: set[str] | None = None) -> dict:
    """Return magic, version, tensor count and the requested metadata keys."""
    path = Path(path)
    if not path.is_file():
        raise GGUFError(f"{path} does not exist")
    wanted = keys or {
        "general.architecture", "general.name", "general.size_label", "general.file_type",
        "general.license", "llama.context_length", "llama.embedding_length",
        "llama.block_count", "tokenizer.ggml.model",
    }
    with path.open("rb") as fh:
        magic = fh.read(4)
        if magic != MAGIC:
            raise GGUFError(f"{path.name}: not a GGUF file (magic {magic!r})")
        version = _U32.unpack(fh.read(4))[0]
        n_tensors = _STRLEN.unpack(fh.read(8))[0]
        n_kv = _STRLEN.unpack(fh.read(8))[0]
        meta: dict = {}
        for _ in range(n_kv):
            key = _read_string(fh)
            kind = _U32.unpack(fh.read(4))[0]
            value = _read_value(fh, kind)
            if key in wanted:
                meta[key] = value
    return {"path": str(path), "bytes": path.stat().st_size, "magic": magic.decode(),
            "version": version, "tensors": n_tensors, "metadata": meta}


def file_type_label(file_type: int | None) -> str:
    """GGUF `general.file_type` for the quantizations this project uses."""
    if file_type is None:
        return "unknown"
    return {0: "f32", 1: "f16", 2: "q4_0", 3: "q4_1", 7: "q8_0", 8: "q5_0", 9: "q5_1",
            10: "q2_k", 11: "q3_k_s", 12: "q3_k_m", 13: "q3_k_l", 14: "q4_k_s",
            15: "q4_k_m", 16: "q5_k_s", 17: "q5_k_m", 18: "q6_k"}.get(file_type, f"type-{file_type}")
