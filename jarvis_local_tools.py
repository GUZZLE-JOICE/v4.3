"""Offline-first local utility tools for JARVIS.

Every tool in this module works without an account, API key, or third-party
web service.  The dispatcher is deliberately allowlisted: a model or webpage
cannot turn a tool request into an arbitrary shell command.
"""

from __future__ import annotations

import ast
import base64
import binascii
import csv
import datetime as dt
import hashlib
import io
import json
import math
import operator
import os
import platform
import re
import secrets
import shutil
import socket
import string
import subprocess
import time
import urllib.parse
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


MAX_TEXT = 250_000
MAX_FILE_READ = 24 * 1024 * 1024
MAX_SCAN_FILES = 20_000
MAX_RESULTS = 250


@dataclass(frozen=True)
class ToolSpec:
    name: str
    label: str
    category: str
    description: str
    inputs: tuple[dict[str, Any], ...]
    handler: Callable[[dict[str, Any]], Any]
    writes_files: bool = False
    voice_examples: tuple[str, ...] = ()

    def public(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "category": self.category,
            "description": self.description,
            "inputs": [dict(item) for item in self.inputs],
            "writes_files": self.writes_files,
            "voice_examples": list(self.voice_examples),
        }


def _field(name: str, label: str, kind: str = "text", **extra: Any) -> dict[str, Any]:
    return {"name": name, "label": label, "type": kind, **extra}


def _text(data: dict[str, Any], key: str, *, limit: int = MAX_TEXT, required: bool = True) -> str:
    value = str(data.get(key) or "")
    if required and not value.strip():
        raise ValueError(f"{key.replace('_', ' ').title()} is required.")
    if len(value) > limit:
        raise ValueError(f"{key.replace('_', ' ').title()} is too long.")
    return value


def _number(data: dict[str, Any], key: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        value = float(data.get(key))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key.replace('_', ' ').title()} must be a number.") from exc
    if not math.isfinite(value):
        raise ValueError(f"{key.replace('_', ' ').title()} must be finite.")
    if minimum is not None and value < minimum:
        raise ValueError(f"{key.replace('_', ' ').title()} must be at least {minimum}.")
    if maximum is not None and value > maximum:
        raise ValueError(f"{key.replace('_', ' ').title()} must be at most {maximum}.")
    return value


def _path(data: dict[str, Any], key: str, *, must_exist: bool = True) -> Path:
    raw = _text(data, key, limit=4096).strip().strip('"')
    path = Path(os.path.expandvars(os.path.expanduser(raw)))
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve(strict=False)
    if must_exist and not path.exists():
        raise ValueError(f"Path does not exist: {path}")
    return path


def _human_bytes(value: int | float) -> str:
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(size) < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TiB"


_BIN_OPS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS: dict[type[ast.unaryop], Callable[[float], float]] = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_MATH_NAMES: dict[str, float | Callable[..., float]] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "abs": abs,
    "round": round,
    "ceil": math.ceil,
    "floor": math.floor,
}


def _eval_math(node: ast.AST, depth: int = 0) -> float:
    if depth > 16:
        raise ValueError("Expression is too complex.")
    if isinstance(node, ast.Expression):
        return _eval_math(node.body, depth + 1)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left, right = _eval_math(node.left, depth + 1), _eval_math(node.right, depth + 1)
        if isinstance(node.op, ast.Pow) and (abs(right) > 12 or abs(left) > 1_000_000):
            raise ValueError("Exponent is too large.")
        result = _BIN_OPS[type(node.op)](left, right)
        if not math.isfinite(result) or abs(result) > 1e100:
            raise ValueError("Result is outside the safe calculator range.")
        return float(result)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return float(_UNARY_OPS[type(node.op)](_eval_math(node.operand, depth + 1)))
    if isinstance(node, ast.Name) and node.id in _MATH_NAMES and isinstance(_MATH_NAMES[node.id], (int, float)):
        return float(_MATH_NAMES[node.id])
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _MATH_NAMES:
        fn = _MATH_NAMES[node.func.id]
        if not callable(fn) or node.keywords or len(node.args) > 3:
            raise ValueError("Unsupported calculator call.")
        return float(fn(*[_eval_math(arg, depth + 1) for arg in node.args]))
    raise ValueError("Use numbers, normal math operators, and supported math functions only.")


def _calculator(data: dict[str, Any]) -> dict[str, Any]:
    expression = _text(data, "expression", limit=500).replace("^", "**")
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_math(tree)
    except (SyntaxError, ZeroDivisionError, OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"Could not calculate that: {exc}") from exc
    shown: int | float = int(result) if result.is_integer() and abs(result) < 2**53 else round(result, 12)
    return {"result": shown, "summary": f"{expression} = {shown}"}


def _percentage(data: dict[str, Any]) -> dict[str, Any]:
    value = _number(data, "value")
    percent = _number(data, "percent")
    result = value * percent / 100
    return {"result": result, "summary": f"{percent:g}% of {value:g} is {result:g}."}


_UNITS: dict[str, tuple[str, float, float]] = {
    "mm": ("length", 0.001, 0), "cm": ("length", 0.01, 0), "m": ("length", 1, 0), "km": ("length", 1000, 0),
    "in": ("length", 0.0254, 0), "ft": ("length", 0.3048, 0), "yd": ("length", 0.9144, 0), "mi": ("length", 1609.344, 0),
    "mg": ("mass", 0.000001, 0), "g": ("mass", 0.001, 0), "kg": ("mass", 1, 0), "oz": ("mass", 0.028349523125, 0), "lb": ("mass", 0.45359237, 0),
    "ml": ("volume", 0.000001, 0), "l": ("volume", 0.001, 0), "tsp": ("volume", 0.00000492892159375, 0), "tbsp": ("volume", 0.00001478676478125, 0), "cup": ("volume", 0.0002365882365, 0), "gal": ("volume", 0.003785411784, 0),
    "c": ("temperature", 1, 0), "f": ("temperature", 5 / 9, -32), "k": ("temperature", 1, -273.15),
    "b": ("data", 1, 0), "kb": ("data", 1000, 0), "mb": ("data", 1_000_000, 0), "gb": ("data", 1_000_000_000, 0), "tb": ("data", 1_000_000_000_000, 0),
    "kib": ("data", 1024, 0), "mib": ("data", 1024**2, 0), "gib": ("data", 1024**3, 0), "tib": ("data", 1024**4, 0),
}


def _convert_units(data: dict[str, Any]) -> dict[str, Any]:
    value = _number(data, "value")
    source = _text(data, "from_unit", limit=20).strip().casefold()
    target = _text(data, "to_unit", limit=20).strip().casefold()
    if source not in _UNITS or target not in _UNITS:
        raise ValueError("Unknown unit. Try mm, cm, m, km, in, ft, kg, lb, L, cup, C, F, MB, or GiB.")
    source_kind, source_scale, source_offset = _UNITS[source]
    target_kind, target_scale, target_offset = _UNITS[target]
    if source_kind != target_kind:
        raise ValueError("Those units measure different things.")
    if source_kind == "temperature":
        celsius = (value + source_offset) * source_scale
        result = celsius / target_scale - target_offset
    else:
        result = value * source_scale / target_scale
    return {"result": result, "summary": f"{value:g} {source} = {result:.10g} {target}."}


def _parse_date(value: str) -> dt.datetime:
    cleaned = value.strip().replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(cleaned)
    except ValueError:
        try:
            return dt.datetime.combine(dt.date.fromisoformat(cleaned), dt.time())
        except ValueError as exc:
            raise ValueError("Use an ISO date such as 2026-08-14 or 2026-08-14T15:30:00.") from exc


def _date_difference(data: dict[str, Any]) -> dict[str, Any]:
    start, end = _parse_date(_text(data, "start", limit=80)), _parse_date(_text(data, "end", limit=80))
    seconds = (end - start).total_seconds()
    return {"seconds": seconds, "days": seconds / 86400, "summary": f"Difference: {seconds / 86400:.4g} days ({seconds:g} seconds)."}


def _timestamp_converter(data: dict[str, Any]) -> dict[str, Any]:
    raw = _text(data, "value", limit=80).strip()
    if re.fullmatch(r"-?\d+(?:\.\d+)?", raw):
        instant = dt.datetime.fromtimestamp(float(raw), tz=dt.timezone.utc)
    else:
        instant = _parse_date(raw)
        if instant.tzinfo is None:
            instant = instant.astimezone()
    return {"unix": instant.timestamp(), "local": instant.astimezone().isoformat(), "utc": instant.astimezone(dt.timezone.utc).isoformat(), "summary": instant.astimezone().isoformat()}


def _local_time(_: dict[str, Any]) -> dict[str, Any]:
    now = dt.datetime.now().astimezone()
    return {"iso": now.isoformat(), "timezone": str(now.tzinfo), "unix": now.timestamp(), "summary": now.strftime("%A, %B %d, %Y at %I:%M:%S %p %Z")}


def _countdown_plan(data: dict[str, Any]) -> dict[str, Any]:
    seconds = _number(data, "seconds", minimum=1, maximum=31_536_000)
    target = dt.datetime.now().astimezone() + dt.timedelta(seconds=seconds)
    return {"seconds": seconds, "target": target.isoformat(), "summary": f"Target time: {target.strftime('%I:%M:%S %p on %b %d, %Y')}"}


def _text_stats(data: dict[str, Any]) -> dict[str, Any]:
    value = _text(data, "text", required=False)
    words = re.findall(r"\b[\w'-]+\b", value, re.UNICODE)
    lines = value.count("\n") + (1 if value else 0)
    sentences = len(re.findall(r"[.!?]+(?:\s|$)", value))
    result = {"characters": len(value), "characters_no_spaces": len(re.sub(r"\s", "", value)), "words": len(words), "lines": lines, "sentences": sentences}
    result["summary"] = f"{result['words']} words, {result['characters']} characters, {lines} lines, {sentences} sentences."
    return result


def _text_case(data: dict[str, Any]) -> dict[str, Any]:
    value, mode = _text(data, "text", required=False), _text(data, "mode", limit=30).strip().casefold()
    handlers = {
        "upper": str.upper, "lower": str.lower, "title": str.title, "sentence": lambda x: x[:1].upper() + x[1:].lower(),
        "snake": lambda x: re.sub(r"[^a-z0-9]+", "_", x.casefold()).strip("_"),
        "kebab": lambda x: re.sub(r"[^a-z0-9]+", "-", x.casefold()).strip("-"),
        "camel": lambda x: (lambda parts: (parts[0] + "".join(p.title() for p in parts[1:])) if parts else "")(re.findall(r"[A-Za-z0-9]+", x)),
    }
    if mode not in handlers:
        raise ValueError("Mode must be upper, lower, title, sentence, snake, kebab, or camel.")
    result = handlers[mode](value)
    return {"text": result, "summary": result}


def _sort_lines(data: dict[str, Any]) -> dict[str, Any]:
    lines = _text(data, "text", required=False).splitlines()
    reverse = str(data.get("direction") or "ascending").casefold().startswith("desc")
    lines.sort(key=str.casefold, reverse=reverse)
    result = "\n".join(lines)
    return {"text": result, "lines": len(lines), "summary": result}


def _unique_lines(data: dict[str, Any]) -> dict[str, Any]:
    seen: set[str] = set()
    output: list[str] = []
    for line in _text(data, "text", required=False).splitlines():
        key = line.casefold() if bool(data.get("ignore_case", True)) else line
        if key not in seen:
            seen.add(key)
            output.append(line)
    result = "\n".join(output)
    return {"text": result, "lines": len(output), "summary": result}


def _find_replace(data: dict[str, Any]) -> dict[str, Any]:
    value = _text(data, "text", required=False)
    find = _text(data, "find", limit=10_000)
    replacement = _text(data, "replacement", limit=10_000, required=False)
    result = value.replace(find, replacement)
    return {"text": result, "replacements": value.count(find), "summary": result}


def _regex_test(data: dict[str, Any]) -> dict[str, Any]:
    pattern = _text(data, "pattern", limit=500)
    value = _text(data, "text", required=False)
    try:
        compiled = re.compile(pattern, re.I if bool(data.get("ignore_case", False)) else 0)
    except re.error as exc:
        raise ValueError(f"Invalid regular expression: {exc}") from exc
    matches = []
    started = time.monotonic()
    for match in compiled.finditer(value):
        matches.append({"text": match.group(0), "start": match.start(), "end": match.end(), "groups": list(match.groups())})
        if len(matches) >= 100 or time.monotonic() - started > 0.5:
            break
    return {"matches": matches, "count": len(matches), "summary": f"Found {len(matches)} match(es)."}


def _json_format(data: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(_text(data, "text"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    result = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=bool(data.get("sort_keys", False)))
    return {"text": result, "summary": result}


def _json_minify(data: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(_text(data, "text"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    result = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    return {"text": result, "summary": result}


def _csv_preview(data: dict[str, Any]) -> dict[str, Any]:
    raw = _text(data, "text")
    rows = list(csv.reader(io.StringIO(raw)))[:101]
    width = max((len(row) for row in rows), default=0)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    return {"rows": normalized, "row_count": max(0, len(rows) - 1), "columns": width, "summary": f"Previewed {len(rows)} row(s) and {width} column(s)."}


def _simple_text_transform(data: dict[str, Any], operation: str) -> dict[str, Any]:
    value = _text(data, "text", required=False)
    if operation == "url_encode": result = urllib.parse.quote(value, safe="")
    elif operation == "url_decode": result = urllib.parse.unquote(value)
    elif operation == "base64_encode": result = base64.b64encode(value.encode("utf-8")).decode("ascii")
    else:
        try: result = base64.b64decode(value.encode("ascii"), validate=True).decode("utf-8")
        except (UnicodeDecodeError, binascii.Error) as exc: raise ValueError("That is not valid UTF-8 base64 text.") from exc
    return {"text": result, "summary": result}


def _hash_text(data: dict[str, Any]) -> dict[str, Any]:
    value = _text(data, "text", required=False).encode("utf-8")
    algorithm = _text(data, "algorithm", limit=20).strip().casefold() or "sha256"
    if algorithm not in {"sha256", "sha512", "sha1", "md5"}:
        raise ValueError("Algorithm must be sha256, sha512, sha1, or md5.")
    digest = hashlib.new(algorithm, value).hexdigest()
    return {"algorithm": algorithm, "digest": digest, "summary": digest}


def _uuid_generator(_: dict[str, Any]) -> dict[str, Any]:
    value = str(uuid.uuid4())
    return {"uuid": value, "summary": value}


def _password_generator(data: dict[str, Any]) -> dict[str, Any]:
    length = int(_number(data, "length", minimum=8, maximum=128))
    alphabet = string.ascii_letters + string.digits + "!@#$%*-_+?"
    value = "".join(secrets.choice(alphabet) for _ in range(length))
    return {"password": value, "summary": value}


def _color_converter(data: dict[str, Any]) -> dict[str, Any]:
    raw = _text(data, "color", limit=80).strip()
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", raw)
    if match:
        value = match.group(1)
        r, g, b = int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    else:
        rgb = re.fullmatch(r"\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*", raw)
        if not rgb:
            raise ValueError("Use #RRGGBB or R, G, B.")
        r, g, b = (int(rgb.group(i)) for i in range(1, 4))
        if max(r, g, b) > 255:
            raise ValueError("RGB values must be 0-255.")
    hex_value = f"#{r:02X}{g:02X}{b:02X}"
    return {"hex": hex_value, "rgb": [r, g, b], "summary": f"{hex_value} · rgb({r}, {g}, {b})"}


def _file_info(data: dict[str, Any]) -> dict[str, Any]:
    path = _path(data, "path")
    stat = path.stat()
    return {"path": str(path), "name": path.name, "type": "directory" if path.is_dir() else "file", "size": stat.st_size, "size_human": _human_bytes(stat.st_size), "modified": dt.datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(), "summary": f"{path.name}: {_human_bytes(stat.st_size)}, modified {dt.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')}."}


def _stream_hash(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _file_hash(data: dict[str, Any]) -> dict[str, Any]:
    path = _path(data, "path")
    if not path.is_file(): raise ValueError("Choose a file, not a folder.")
    algorithm = _text(data, "algorithm", limit=20).strip().casefold() or "sha256"
    if algorithm not in {"sha256", "sha512", "sha1", "md5"}: raise ValueError("Unsupported hash algorithm.")
    digest = _stream_hash(path, algorithm)
    return {"path": str(path), "algorithm": algorithm, "digest": digest, "summary": digest}


def _text_preview(data: dict[str, Any]) -> dict[str, Any]:
    path = _path(data, "path")
    if not path.is_file(): raise ValueError("Choose a text file.")
    if path.stat().st_size > MAX_FILE_READ: raise ValueError("File is over the 24 MiB preview limit.")
    limit = int(_number(data, "characters", minimum=100, maximum=100_000))
    value = path.read_text(encoding="utf-8", errors="replace")[:limit]
    return {"path": str(path), "text": value, "truncated": path.stat().st_size > len(value.encode("utf-8")), "summary": value}


def _walk_files(root: Path):
    seen = 0
    for base, directories, files in os.walk(root):
        directories[:] = [name for name in directories if name not in {".git", "node_modules", "__pycache__", "$Recycle.Bin", "System Volume Information"}]
        for name in files:
            seen += 1
            if seen > MAX_SCAN_FILES: return
            yield Path(base) / name


def _file_search(data: dict[str, Any]) -> dict[str, Any]:
    root = _path(data, "folder")
    if not root.is_dir(): raise ValueError("Choose a folder to search.")
    query = _text(data, "query", limit=200).casefold()
    results = [str(path) for path in _walk_files(root) if query in path.name.casefold()][:MAX_RESULTS]
    return {"matches": results, "count": len(results), "summary": f"Found {len(results)} matching file(s)."}


def _folder_size(data: dict[str, Any]) -> dict[str, Any]:
    root = _path(data, "folder")
    if not root.is_dir(): raise ValueError("Choose a folder.")
    total = 0; count = 0
    for path in _walk_files(root):
        try: total += path.stat().st_size; count += 1
        except OSError: pass
    return {"folder": str(root), "bytes": total, "size_human": _human_bytes(total), "files": count, "summary": f"{_human_bytes(total)} across {count} files."}


def _duplicate_finder(data: dict[str, Any]) -> dict[str, Any]:
    root = _path(data, "folder")
    if not root.is_dir(): raise ValueError("Choose a folder.")
    by_size: dict[int, list[Path]] = {}
    for path in _walk_files(root):
        try:
            size = path.stat().st_size
            if size: by_size.setdefault(size, []).append(path)
        except OSError: pass
    duplicates: list[dict[str, Any]] = []
    for size, paths in by_size.items():
        if len(paths) < 2: continue
        by_hash: dict[str, list[str]] = {}
        for path in paths:
            try: by_hash.setdefault(_stream_hash(path), []).append(str(path))
            except OSError: pass
        for digest, items in by_hash.items():
            if len(items) > 1:
                duplicates.append({"sha256": digest, "size": size, "size_human": _human_bytes(size), "files": items})
                if len(duplicates) >= 100: break
        if len(duplicates) >= 100: break
    return {"groups": duplicates, "count": len(duplicates), "summary": f"Found {len(duplicates)} duplicate group(s). Nothing was deleted."}


def _zip_list(data: dict[str, Any]) -> dict[str, Any]:
    path = _path(data, "path")
    if not path.is_file(): raise ValueError("Choose a ZIP file.")
    with zipfile.ZipFile(path) as archive:
        entries = [{"name": info.filename, "size": info.file_size, "compressed": info.compress_size} for info in archive.infolist()[:MAX_RESULTS]]
    return {"entries": entries, "count": len(entries), "summary": f"ZIP contains {len(entries)} listed item(s)."}


def _pdf_extract(data: dict[str, Any]) -> dict[str, Any]:
    path = _path(data, "path")
    if not path.is_file() or path.suffix.casefold() != ".pdf": raise ValueError("Choose a PDF file.")
    if path.stat().st_size > MAX_FILE_READ: raise ValueError("PDF is over the 24 MiB local extraction limit.")
    try:
        from pypdf import PdfReader
    except ImportError as exc: raise RuntimeError("The bundled PDF reader is unavailable.") from exc
    reader = PdfReader(str(path)); text = "\n\n".join((page.extract_text() or "") for page in reader.pages)[:MAX_TEXT]
    return {"pages": len(reader.pages), "text": text, "summary": text or "No selectable text was found."}


def _docx_extract(data: dict[str, Any]) -> dict[str, Any]:
    path = _path(data, "path")
    if not path.is_file() or path.suffix.casefold() != ".docx": raise ValueError("Choose a DOCX file.")
    if path.stat().st_size > MAX_FILE_READ: raise ValueError("DOCX is over the 24 MiB local extraction limit.")
    try:
        from docx import Document
    except ImportError as exc: raise RuntimeError("The bundled DOCX reader is unavailable.") from exc
    document = Document(str(path)); text = "\n".join(paragraph.text for paragraph in document.paragraphs)[:MAX_TEXT]
    return {"paragraphs": len(document.paragraphs), "text": text, "summary": text or "No paragraph text was found."}


def _image_dimensions(path: Path) -> tuple[str, int, int]:
    with path.open("rb") as handle:
        head = handle.read(32)
        if head.startswith(b"\x89PNG\r\n\x1a\n"):
            return "PNG", int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
        if head[:6] in {b"GIF87a", b"GIF89a"}:
            return "GIF", int.from_bytes(head[6:8], "little"), int.from_bytes(head[8:10], "little")
        if head.startswith(b"BM"):
            return "BMP", int.from_bytes(head[18:22], "little", signed=True), abs(int.from_bytes(head[22:26], "little", signed=True))
        if head.startswith(b"\xff\xd8"):
            handle.seek(2)
            while True:
                marker_start = handle.read(1)
                if not marker_start: break
                if marker_start != b"\xff": continue
                marker = handle.read(1)
                while marker == b"\xff": marker = handle.read(1)
                if marker in {bytes([code]) for code in range(0xC0, 0xC4)} | {bytes([code]) for code in range(0xC5, 0xC8)} | {bytes([code]) for code in range(0xC9, 0xCC)} | {bytes([code]) for code in range(0xCD, 0xD0)}:
                    length = int.from_bytes(handle.read(2), "big"); payload = handle.read(length - 2)
                    return "JPEG", int.from_bytes(payload[3:5], "big"), int.from_bytes(payload[1:3], "big")
                length_bytes = handle.read(2)
                if len(length_bytes) < 2: break
                handle.seek(max(0, int.from_bytes(length_bytes, "big") - 2), 1)
    raise ValueError("Supported image types are PNG, JPEG, GIF, and BMP.")


def _image_info(data: dict[str, Any]) -> dict[str, Any]:
    path = _path(data, "path")
    if not path.is_file(): raise ValueError("Choose an image file.")
    kind, width, height = _image_dimensions(path)
    return {"format": kind, "width": width, "height": height, "bytes": path.stat().st_size, "summary": f"{kind} · {width} × {height} · {_human_bytes(path.stat().st_size)}"}


def _system_info(_: dict[str, Any]) -> dict[str, Any]:
    result = {"system": platform.system(), "release": platform.release(), "version": platform.version(), "machine": platform.machine(), "processor": platform.processor(), "cpu_count": os.cpu_count() or 1, "python": platform.python_version(), "hostname": socket.gethostname()}
    result["summary"] = f"{result['system']} {result['release']} on {result['machine']}, {result['cpu_count']} logical CPU cores."
    return result


def _disk_usage(data: dict[str, Any]) -> dict[str, Any]:
    raw = str(data.get("path") or (Path.home().anchor or "/"))
    path = Path(os.path.expandvars(os.path.expanduser(raw))).resolve(strict=False)
    usage = shutil.disk_usage(path)
    return {"path": str(path), "total": usage.total, "used": usage.used, "free": usage.free, "total_human": _human_bytes(usage.total), "used_human": _human_bytes(usage.used), "free_human": _human_bytes(usage.free), "summary": f"{_human_bytes(usage.free)} free of {_human_bytes(usage.total)}."}


def _process_list(data: dict[str, Any]) -> dict[str, Any]:
    query = str(data.get("query") or "").strip().casefold()
    rows: list[dict[str, str]] = []
    try:
        if os.name == "nt":
            output = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=6, check=False).stdout
            for row in csv.reader(io.StringIO(output)):
                if len(row) >= 2 and (not query or query in row[0].casefold()): rows.append({"name": row[0], "pid": row[1], "memory": row[4] if len(row) > 4 else ""})
        else:
            output = subprocess.run(["ps", "-eo", "pid=,comm="], capture_output=True, text=True, timeout=6, check=False).stdout
            for line in output.splitlines():
                parts = line.strip().split(None, 1)
                if len(parts) == 2 and (not query or query in parts[1].casefold()): rows.append({"pid": parts[0], "name": parts[1]})
    except (OSError, subprocess.SubprocessError) as exc: raise RuntimeError(f"Could not list processes: {exc}") from exc
    rows = rows[:MAX_RESULTS]
    return {"processes": rows, "count": len(rows), "summary": f"Listed {len(rows)} running process(es)."}


def _dns_lookup(data: dict[str, Any]) -> dict[str, Any]:
    host = _text(data, "host", limit=253).strip()
    try: addresses = sorted({item[4][0] for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)})
    except socket.gaierror as exc: raise ValueError(f"DNS lookup failed: {exc}") from exc
    return {"host": host, "addresses": addresses, "summary": f"{host}: {', '.join(addresses)}"}


def _port_check(data: dict[str, Any]) -> dict[str, Any]:
    host = _text(data, "host", limit=253).strip()
    port = int(_number(data, "port", minimum=1, maximum=65535))
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=2.5): open_state = True
    except OSError: open_state = False
    elapsed = round((time.monotonic() - started) * 1000, 1)
    return {"host": host, "port": port, "open": open_state, "milliseconds": elapsed, "summary": f"{host}:{port} is {'open' if open_state else 'closed or unreachable'} ({elapsed:g} ms)."}


def _clipboard_read(_: dict[str, Any]) -> dict[str, Any]:
    try:
        import pyperclip
        value = str(pyperclip.paste() or "")[:MAX_TEXT]
    except Exception as exc: raise RuntimeError(f"Clipboard could not be read: {exc}") from exc
    return {"text": value, "summary": value or "Clipboard is empty."}


def _screenshot(data: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    try:
        import pyautogui
        image = pyautogui.screenshot()
    except Exception as exc: raise RuntimeError(f"Screenshot could not be captured: {exc}") from exc
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"jarvis-screenshot-{dt.datetime.now():%Y%m%d-%H%M%S}.png"
    image.save(path)
    return {"path": str(path), "summary": f"Saved screenshot to {path}."}


def _create_note(data: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    title = re.sub(r"[^A-Za-z0-9 _.-]+", "", _text(data, "title", limit=120)).strip() or "Jarvis note"
    content = _text(data, "text", required=False)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / (title[:80].rstrip(". ") + ".txt")
    if path.exists(): path = output_dir / (title[:70].rstrip(". ") + f"-{int(time.time())}.txt")
    path.write_text(content, encoding="utf-8")
    return {"path": str(path), "summary": f"Created note {path.name}."}


def _zip_create(data: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    source = _path(data, "path")
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9 _.-]+", "", str(data.get("name") or source.name or "archive")).strip().rstrip(". ") or "archive"
    path = output_dir / (Path(safe_name).stem[:80] + ".zip")
    if path.exists(): path = output_dir / (Path(safe_name).stem[:70] + f"-{int(time.time())}.zip")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        if source.is_file(): archive.write(source, arcname=source.name)
        else:
            for item in _walk_files(source):
                try: archive.write(item, arcname=str(item.relative_to(source.parent)))
                except OSError: pass
    return {"path": str(path), "size": path.stat().st_size, "summary": f"Created {path.name} ({_human_bytes(path.stat().st_size)})."}


class LocalToolHub:
    """Catalog and execute deterministic, no-account local tools."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir) / "local_tools"
        self.output_dir = self.data_dir / "outputs"
        self._specs = self._build_specs()

    def _build_specs(self) -> dict[str, ToolSpec]:
        specs = [
            ToolSpec("calculator", "Calculator", "QUICK", "Safely evaluate normal math without running code.", (_field("expression", "Expression", "textarea", placeholder="(12 * 8) + sqrt(81)"),), _calculator, voice_examples=("Jarvis calculate 12 times 8",)),
            ToolSpec("percentage", "Percentage", "QUICK", "Calculate a percentage of a number.", (_field("value", "Value", "number"), _field("percent", "Percent", "number")), _percentage),
            ToolSpec("unit_converter", "Unit Converter", "QUICK", "Convert length, mass, volume, temperature, or data units.", (_field("value", "Value", "number"), _field("from_unit", "From unit", placeholder="mm"), _field("to_unit", "To unit", placeholder="in")), _convert_units, voice_examples=("Jarvis convert 100 millimeters to inches",)),
            ToolSpec("date_difference", "Date Difference", "QUICK", "Find the exact time between two ISO dates.", (_field("start", "Start", placeholder="2026-08-14"), _field("end", "End", placeholder="2026-09-01")), _date_difference),
            ToolSpec("timestamp_converter", "Timestamp Converter", "QUICK", "Convert an ISO date or Unix timestamp.", (_field("value", "Date or timestamp"),), _timestamp_converter),
            ToolSpec("local_time", "Local Time", "QUICK", "Show this computer's exact local time and timezone.", (), _local_time, voice_examples=("Jarvis what time is it",)),
            ToolSpec("countdown_plan", "Countdown Target", "QUICK", "Calculate when a countdown will finish.", (_field("seconds", "Seconds", "number", value="300"),), _countdown_plan),
            ToolSpec("text_stats", "Text Stats", "TEXT", "Count words, characters, lines, and sentences.", (_field("text", "Text", "textarea"),), _text_stats),
            ToolSpec("text_case", "Text Case", "TEXT", "Convert text to upper, lower, title, sentence, snake, kebab, or camel case.", (_field("text", "Text", "textarea"), _field("mode", "Mode", "select", options=["upper", "lower", "title", "sentence", "snake", "kebab", "camel"])), _text_case),
            ToolSpec("sort_lines", "Sort Lines", "TEXT", "Sort lines alphabetically.", (_field("text", "Lines", "textarea"), _field("direction", "Direction", "select", options=["ascending", "descending"])), _sort_lines),
            ToolSpec("unique_lines", "Remove Duplicate Lines", "TEXT", "Keep the first copy of every line.", (_field("text", "Lines", "textarea"), _field("ignore_case", "Ignore case", "checkbox", value=True)), _unique_lines),
            ToolSpec("find_replace", "Find & Replace", "TEXT", "Replace literal text without changing a file.", (_field("text", "Text", "textarea"), _field("find", "Find"), _field("replacement", "Replacement")), _find_replace),
            ToolSpec("regex_test", "Regex Tester", "TEXT", "Test a regular expression with bounded output.", (_field("pattern", "Pattern"), _field("text", "Text", "textarea"), _field("ignore_case", "Ignore case", "checkbox")), _regex_test),
            ToolSpec("json_format", "JSON Formatter", "TEXT", "Validate and format JSON.", (_field("text", "JSON", "textarea"), _field("sort_keys", "Sort keys", "checkbox")), _json_format),
            ToolSpec("json_minify", "JSON Minifier", "TEXT", "Validate and minify JSON.", (_field("text", "JSON", "textarea"),), _json_minify),
            ToolSpec("csv_preview", "CSV Preview", "TEXT", "Parse CSV into a safe row preview.", (_field("text", "CSV", "textarea"),), _csv_preview),
            ToolSpec("url_encode", "URL Encode", "ENCODE", "Percent-encode text for a URL.", (_field("text", "Text", "textarea"),), lambda data: _simple_text_transform(data, "url_encode")),
            ToolSpec("url_decode", "URL Decode", "ENCODE", "Decode percent-encoded text.", (_field("text", "Text", "textarea"),), lambda data: _simple_text_transform(data, "url_decode")),
            ToolSpec("base64_encode", "Base64 Encode", "ENCODE", "Encode UTF-8 text as Base64.", (_field("text", "Text", "textarea"),), lambda data: _simple_text_transform(data, "base64_encode")),
            ToolSpec("base64_decode", "Base64 Decode", "ENCODE", "Decode Base64 into UTF-8 text.", (_field("text", "Base64", "textarea"),), lambda data: _simple_text_transform(data, "base64_decode")),
            ToolSpec("hash_text", "Hash Text", "ENCODE", "Create a SHA or MD5 checksum for text.", (_field("text", "Text", "textarea"), _field("algorithm", "Algorithm", "select", options=["sha256", "sha512", "sha1", "md5"])), _hash_text),
            ToolSpec("uuid_generator", "UUID Generator", "GENERATE", "Generate a random UUID v4 locally.", (), _uuid_generator, voice_examples=("Jarvis generate a UUID",)),
            ToolSpec("password_generator", "Password Generator", "GENERATE", "Generate a strong random password locally.", (_field("length", "Length", "number", value="20"),), _password_generator, voice_examples=("Jarvis generate a 20 character password",)),
            ToolSpec("color_converter", "Color Converter", "GENERATE", "Convert between HEX and RGB colors.", (_field("color", "HEX or RGB", placeholder="#00E5FF or 0,229,255"),), _color_converter),
            ToolSpec("file_info", "File Info", "FILES", "Read a file or folder's size and modified time.", (_field("path", "Path", placeholder="C:\\Users\\You\\Downloads\\file.stl"),), _file_info),
            ToolSpec("file_hash", "File Checksum", "FILES", "Calculate a checksum without uploading the file.", (_field("path", "File path"), _field("algorithm", "Algorithm", "select", options=["sha256", "sha512", "sha1", "md5"])), _file_hash),
            ToolSpec("text_preview", "Text File Preview", "FILES", "Read the beginning of a local text file.", (_field("path", "File path"), _field("characters", "Characters", "number", value="12000")), _text_preview),
            ToolSpec("file_search", "Find Files", "FILES", "Search filenames inside a folder; skips system/build caches.", (_field("folder", "Folder"), _field("query", "Filename contains")), _file_search, voice_examples=("Jarvis find files named invoice in Downloads",)),
            ToolSpec("folder_size", "Folder Size", "FILES", "Measure a folder without changing it.", (_field("folder", "Folder"),), _folder_size),
            ToolSpec("duplicate_finder", "Duplicate Finder", "FILES", "Find byte-identical files; never deletes anything.", (_field("folder", "Folder"),), _duplicate_finder),
            ToolSpec("zip_list", "ZIP Inspector", "FILES", "List a ZIP archive without extracting it.", (_field("path", "ZIP path"),), _zip_list),
            ToolSpec("pdf_extract", "PDF Text", "FILES", "Extract selectable text from a local PDF.", (_field("path", "PDF path"),), _pdf_extract),
            ToolSpec("docx_extract", "DOCX Text", "FILES", "Extract paragraph text from a local Word document.", (_field("path", "DOCX path"),), _docx_extract),
            ToolSpec("image_info", "Image Info", "FILES", "Read dimensions for PNG, JPEG, GIF, or BMP.", (_field("path", "Image path"),), _image_info),
            ToolSpec("system_info", "System Info", "SYSTEM", "Show OS, CPU, architecture, and hostname.", (), _system_info, voice_examples=("Jarvis show system info",)),
            ToolSpec("disk_usage", "Disk Usage", "SYSTEM", "Show total, used, and free disk space.", (_field("path", "Drive or path", value=str(Path.home().anchor or "/")),), _disk_usage, voice_examples=("Jarvis how much disk space is free",)),
            ToolSpec("process_list", "Process List", "SYSTEM", "List running processes or filter by name.", (_field("query", "Optional name filter"),), _process_list, voice_examples=("Jarvis list Chrome processes",)),
            ToolSpec("dns_lookup", "DNS Lookup", "SYSTEM", "Resolve a hostname using this PC's DNS settings.", (_field("host", "Hostname", value="example.com"),), _dns_lookup),
            ToolSpec("port_check", "Port Check", "SYSTEM", "Check whether a TCP port is reachable.", (_field("host", "Host", value="127.0.0.1"), _field("port", "Port", "number", value="5015")), _port_check),
            ToolSpec("clipboard_read", "Read Clipboard", "SYSTEM", "Read current text from this PC's clipboard.", (), _clipboard_read),
            ToolSpec("screenshot", "Save Screenshot", "CREATE", "Capture this PC's screen to the JARVIS outputs folder.", (), lambda data: _screenshot(data, self.output_dir), writes_files=True),
            ToolSpec("create_note", "Create Note", "CREATE", "Save a UTF-8 note in the JARVIS outputs folder.", (_field("title", "Title"), _field("text", "Note", "textarea")), lambda data: _create_note(data, self.output_dir), writes_files=True),
            ToolSpec("zip_create", "Create ZIP", "CREATE", "Make a ZIP copy of a file or folder in JARVIS outputs.", (_field("path", "File or folder"), _field("name", "Archive name")), lambda data: _zip_create(data, self.output_dir), writes_files=True),
        ]
        return {spec.name: spec for spec in specs}

    def catalog(self) -> dict[str, Any]:
        tools = [spec.public() for spec in self._specs.values()]
        categories = []
        for spec in self._specs.values():
            if spec.category not in categories: categories.append(spec.category)
        return {"ok": True, "count": len(tools), "categories": categories, "tools": tools, "no_api_required": True, "no_signup_required": True}

    def run(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        spec = self._specs.get(str(name or "").strip())
        if spec is None: raise ValueError("Unknown local tool.")
        started = time.monotonic()
        result = spec.handler(arguments if isinstance(arguments, dict) else {})
        if not isinstance(result, dict): result = {"result": result}
        result.setdefault("summary", json.dumps(result, ensure_ascii=False, default=str)[:2000])
        return {"ok": True, "tool": spec.name, "label": spec.label, "elapsed_ms": round((time.monotonic() - started) * 1000, 2), "result": result}

    def command(self, utterance: str) -> dict[str, Any]:
        text = " ".join(str(utterance or "").strip().split())
        lowered = text.casefold()
        if re.search(r"\b(?:list|show|open) (?:your |the )?(?:local )?tools\b", lowered):
            return {"ok": True, "matched": True, "open_tools": True, "message": f"Opening {len(self._specs)} local tools."}
        match = re.search(r"\b(?:calculate|what is)\s+(.+)$", text, re.I)
        if match:
            try: return {"matched": True, **self.run("calculator", {"expression": match.group(1)})}
            except ValueError: pass
        match = re.search(r"\bconvert\s+(-?\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s+(?:to|in)\s+([a-zA-Z]+)\b", text, re.I)
        if match: return {"matched": True, **self.run("unit_converter", {"value": match.group(1), "from_unit": match.group(2), "to_unit": match.group(3)})}
        if re.search(r"\b(?:generate|make)(?: me)? (?:a )?uuid\b", lowered): return {"matched": True, **self.run("uuid_generator", {})}
        match = re.search(r"\b(?:generate|make)(?: me)? (?:a )?(\d{1,3})?(?: character)? password\b", lowered)
        if match: return {"matched": True, **self.run("password_generator", {"length": int(match.group(1) or 20)})}
        if re.search(r"\b(?:system info|computer info|pc info)\b", lowered): return {"matched": True, **self.run("system_info", {})}
        if re.search(r"\b(?:disk space|disk usage|free space)\b", lowered): return {"matched": True, **self.run("disk_usage", {"path": str(Path.home().anchor or "/")})}
        match = re.search(r"\b(?:dns lookup|resolve)\s+([a-z0-9.-]+)\b", lowered)
        if match: return {"matched": True, **self.run("dns_lookup", {"host": match.group(1)})}
        match = re.search(r"\b(?:check port|is port)\s+(\d{1,5})(?:\s+(?:on|at)\s+([a-z0-9.-]+))?", lowered)
        if match: return {"matched": True, **self.run("port_check", {"port": match.group(1), "host": match.group(2) or "127.0.0.1"})}
        if re.search(r"\b(?:what time is it|local time|current time)\b", lowered): return {"matched": True, **self.run("local_time", {})}
        return {"ok": True, "matched": False}

