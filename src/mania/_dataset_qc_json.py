"""Serialization-only support for the explicitly selected Stage 32 models.

Types come from local callers and accepted model annotations, never JSON names.
Constructors own model semantics. This adapter checks JSON shape/scalars first.
"""

import json
import math
from dataclasses import fields, is_dataclass
from pathlib import Path
from types import UnionType
from typing import Any, Literal, TypeVar, Union, get_args, get_origin, get_type_hints

from pydantic import BaseModel

from mania.preprocessing.molecular_partner_metadata_io import (
    SpecializedArtifactWriteResult,
    read_strict_json,
    write_atomic_text,
)

T = TypeVar("T")


def portable_path(value: str) -> Path:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or (
            any(p in ("", ".", "..") for p in value.split("/"))
            or any(c in value for c in ("\\", ":", "~", "$", "%"))
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
        )
    ):
        raise ValueError("Expected portable relative path without traversal")
    return Path(value)


def payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return {n: payload(getattr(value, n)) for n in type(value).model_fields}
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: payload(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Path):
        return value.as_posix()
    if type(value) is tuple:
        return [payload(v) for v in value]
    return value


def decode(value: Any, model: Any) -> Any:
    origin, args = get_origin(model), get_args(model)
    if origin in (Union, UnionType):
        for choice in args:
            try:
                return decode(value, choice)
            except (ValueError, TypeError, OverflowError):
                continue
        raise ValueError("Value does not match any permitted model type")
    if origin is Literal:
        if not any(type(value) is type(a) and value == a for a in args):
            raise ValueError("Invalid exact literal")
        return value
    if origin is tuple:
        if type(value) is not list:
            raise ValueError("Expected JSON array")
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(decode(v, args[0]) for v in value)
        if len(value) != len(args):
            raise ValueError("Invalid fixed tuple length")
        return tuple(decode(v, t) for v, t in zip(value, args, strict=True))
    if model is Path:
        return portable_path(value)
    if model in (str, bool, int, float, type(None)):
        valid = type(value) is model or (model is float and type(value) is int)
        if not valid or (type(value) is float and not math.isfinite(value)):
            raise ValueError("Invalid strict JSON scalar")
        return value
    if is_dataclass(model) or (
        isinstance(model, type) and issubclass(model, BaseModel)
    ):
        constructor: Any = model
        dataclass_fields = fields(model) if is_dataclass(model) else ()
        names = (
            tuple(f.name for f in dataclass_fields)
            if dataclass_fields
            else tuple(constructor.model_fields)
        )
        if type(value) is not dict or set(value) != set(names):
            raise ValueError("Invalid exact JSON object fields")
        hints = get_type_hints(model)
        # Accepted generic canonical tables specialize their row type here.
        if hasattr(model, "_row_type"):
            hints["rows"] = tuple[model._row_type, ...]
        parsed = {n: decode(value[n], hints[n]) for n in names}
        derived = {f.name for f in dataclass_fields if not f.init}
        result = constructor(**{n: v for n, v in parsed.items() if n not in derived})
        if any(parsed[n] != getattr(result, n) for n in derived):
            raise ValueError("Fixed or derived model metadata mismatch")
        return result
    raise TypeError("Unsupported QC serialization type")


def read_model(path: str | Path, model: type[T]) -> T:
    try:
        result: T = decode(read_strict_json(path), model)
        return result
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        raise ValueError(f"Invalid or unreadable {model.__name__} JSON.") from None


def model_bytes(value: T, model: type[T]) -> bytes:
    if type(value) is not model:
        raise ValueError(f"Expected exact {model.__name__}")
    data = payload(value)
    if decode(data, model) != value:
        raise ValueError("Model differs from strict reconstruction")
    return (
        json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    ).encode("utf-8")


def write_model(
    value: T,
    model: type[T],
    path: str | Path,
    *,
    overwrite: bool = False,
) -> SpecializedArtifactWriteResult:
    return write_atomic_text(
        model_bytes(value, model).decode("utf-8"),
        Path(path),
        overwrite=overwrite,
    )
