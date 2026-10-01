# agent/tools.py
import os
import re
import subprocess
from pathlib import Path

MAX_FILE_BYTES = 200_000

# tools.py (append at the bottom)
import contextvars
from langchain_core.tools import tool as lc_tool

_repo_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("repo_path")
_read_files: contextvars.ContextVar[set] = contextvars.ContextVar("read_files")


def set_repo(repo_path: str):
    return (_repo_ctx.set(repo_path), _read_files.set(set()))


def reset_repo(tokens):
    repo_tok, files_tok = tokens
    _read_files.reset(files_tok)
    _repo_ctx.reset(repo_tok)


def get_read_files() -> list[str]:
    try:
        return sorted(_read_files.get())
    except LookupError:
        return []


def _root() -> str:
    try:
        return _repo_ctx.get()
    except LookupError as e:
        raise RuntimeError("repo not set; call set_repo first") from e


def _track(path: str) -> None:
    try:
        _read_files.get().add(path)
    except LookupError:
        pass


@lc_tool
def read_file_tool(path: str, max_bytes: int = MAX_FILE_BYTES) -> str:
    """Read a whole file. Output is line-numbered."""
    _track(path)
    return read_file(_root(), path, max_bytes)


@lc_tool
def read_lines_tool(path: str, start: int, end: int) -> str:
    """Read a line range. Output is line-numbered."""
    _track(path)
    return read_lines(_root(), path, start, end)


@lc_tool
def list_dir_tool(path: str = ".") -> str:
    """List a directory."""
    return list_dir(_root(), path)


@lc_tool
def grep_tool(pattern: str, glob: str = "**/*", max_results: int = 50) -> str:
    """Regex search. Output is path:line: text."""
    return grep(_root(), pattern, glob, max_results)


@lc_tool
def find_symbol_tool(name: str) -> str:
    """Locate a function/class definition by name."""
    return find_symbol(_root(), name)


explorer_toolkit = [
    read_file_tool,
    read_lines_tool,
    list_dir_tool,
    grep_tool,
    find_symbol_tool,
]


def _safe_path(repo_path: str, rel: str) -> Path:
    """Resolve a repo-relative path and refuse anything outside the repo."""
    root = Path(repo_path).resolve()
    target = (root / rel).resolve()
    if root not in target.parents and target != root:
        raise ValueError(f"path escapes repo: {rel}")
    return target


def _numbered(text: str) -> str:
    """Prefix each line with its 1-based line number and a tab."""
    return "\n".join(f"{i}\t{line}" for i, line in enumerate(text.splitlines(), 1))


def read_file(repo_path: str, path: str, max_bytes: int = MAX_FILE_BYTES) -> str:
    p = _safe_path(repo_path, path)
    if not p.is_file():
        return f"ERROR: not a file: {path}"
    data = p.read_bytes()[:max_bytes]
    truncated = p.stat().st_size > max_bytes
    text = data.decode("utf-8", errors="replace")
    out = _numbered(text)
    if truncated:
        out += f"\n... [truncated at {max_bytes} bytes]"
    return out


def read_lines(repo_path: str, path: str, start: int, end: int) -> str:
    p = _safe_path(repo_path, path)
    if not p.is_file():
        return f"ERROR: not a file: {path}"
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, start)
    end = min(len(lines), end)
    return "\n".join(f"{i}\t{lines[i-1]}" for i in range(start, end + 1))


def list_dir(repo_path: str, path: str = ".") -> str:
    p = _safe_path(repo_path, path)
    if not p.is_dir():
        return f"ERROR: not a directory: {path}"
    entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name))
    return "\n".join(f"{'d' if e.is_dir() else 'f'} {e.name}" for e in entries)


def grep(repo_path: str, pattern: str, glob: str = "**/*", max_results: int = 50) -> str:
    root = Path(repo_path).resolve()
    rx = re.compile(pattern)
    hits = []
    for fp in root.glob(glob):
        if not fp.is_file():
            continue
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                rel = fp.relative_to(root)
                hits.append(f"{rel}:{i}: {line.strip()[:200]}")
                if len(hits) >= max_results:
                    return "\n".join(hits) + f"\n... [capped at {max_results}]"
    return "\n".join(hits) if hits else "no matches"


def find_symbol(repo_path: str, name: str) -> str:
    # Cheap heuristic: look for common definition forms. Replace with tree-sitter
    # if you want precision.
    pattern = rf"(def|class|function|const|let|var|fn|func)\s+{re.escape(name)}\b"
    return grep(repo_path, pattern, glob="**/*", max_results=20)


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a whole file. Output is line-numbered.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_bytes": {"type": "integer", "default": MAX_FILE_BYTES},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_lines",
            "description": "Read a line range. Output is line-numbered.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start": {"type": "integer"},
                    "end": {"type": "integer"},
                },
                "required": ["path", "start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List a directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "default": "."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Regex search. Output is path:line: text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "glob": {"type": "string", "default": "**/*"},
                    "max_results": {"type": "integer", "default": 50},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_symbol",
            "description": "Locate a function/class definition by name.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
]

TOOL_FUNCS = {
    "read_file": read_file,
    "read_lines": read_lines,
    "list_dir": list_dir,
    "grep": grep,
    "find_symbol": find_symbol,
}


def dispatch(repo_path: str, name: str, args: dict) -> str:
    fn = TOOL_FUNCS.get(name)
    if not fn:
        return f"ERROR: unknown tool {name}"
    try:
        return fn(repo_path, **args)
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"