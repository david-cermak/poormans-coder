"""Execute context requests and file operations."""

import re
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ReadFileRequest:
    path: str


@dataclass
class GrepRequest:
    pattern: str
    path: str = "."


@dataclass
class ListDirRequest:
    path: str = "."


@dataclass
class WriteFileOp:
    path: str
    content: str


@dataclass
class EditFileOp:
    path: str
    old: str
    new: str
    replace_all: bool = False


def _normalize_whitespace(text: str) -> str:
    """Normalize for matching: trim trailing, collapse runs of spaces."""
    lines = text.split("\n")
    normalized = []
    for line in lines:
        # Preserve leading indent, normalize trailing
        stripped = line.rstrip()
        # Collapse multiple spaces to single (but keep indent)
        if stripped:
            leading = line[: len(line) - len(line.lstrip())]
            rest = " ".join(stripped.split())
            normalized.append(leading + rest)
        else:
            normalized.append("")
    return "\n".join(normalized)


def _find_old_string(content: str, old: str) -> tuple[int, int] | None:
    """Try hard to find old string. Returns (start, end) or None."""
    # Exact match first
    if old in content:
        start = content.index(old)
        return (start, start + len(old))

    # Normalize both and try again
    content_norm = _normalize_whitespace(content)
    old_norm = _normalize_whitespace(old)

    if old_norm in content_norm:
        # Find position in original content - approximate by searching for
        # a substring that survives normalization
        # Simpler: do replacement on normalized, then we need to map back...
        # Actually: do the replacement on normalized content, then "un-normalize"?
        # That's complex. Instead: try line-by-line or chunk matching.
        pass

    # Try matching line by line with normalized comparison
    old_lines = old.strip().split("\n")
    content_lines = content.split("\n")
    if not old_lines:
        return None

    for i in range(len(content_lines) - len(old_lines) + 1):
        window = "\n".join(content_lines[i : i + len(old_lines)])
        if _normalize_whitespace(window) == _normalize_whitespace(old):
            start = sum(len(l) + 1 for l in content_lines[:i]) - (1 if i > 0 else 0)
            if i == 0:
                start = 0
            else:
                start = len("\n".join(content_lines[:i]))
            end = start + len(window)
            return (start, end)

    return None


def read_file(project_root: Path, path: str) -> str:
    """Read file content. Path can be relative to project_root or absolute."""
    proot = project_root.resolve()
    if Path(path).is_absolute():
        p = Path(path).resolve()
    else:
        p = (proot / path).resolve()
    if not str(p).startswith(str(proot)):
        raise ValueError(f"Path outside project: {path}")
    return p.read_text()


def grep(project_root: Path, pattern: str, path: str = ".") -> list[tuple[str, int, str]]:
    """Search for pattern in files. Returns [(file_path, line_num, line_content), ...]."""
    base = project_root / path if path != "." else project_root
    base = base.resolve()
    if not base.exists() or not base.is_dir():
        return []

    results = []
    try:
        regex = re.compile(pattern)
    except re.error:
        regex = re.compile(re.escape(pattern))

    skip_dirs = {".venv", "venv", "__pycache__", ".git", "node_modules"}
    for f in base.rglob("*"):
        if any(part in skip_dirs for part in f.parts):
            continue
        if f.is_file() and not f.name.startswith("."):
            try:
                text = f.read_text(errors="ignore")
                rel = f.relative_to(project_root)
                for i, line in enumerate(text.split("\n"), 1):
                    if regex.search(line):
                        results.append((str(rel), i, line.strip()))
            except Exception:
                pass

    return results


def list_dir(project_root: Path, path: str = ".") -> list[tuple[str, bool]]:
    """List directory. Returns [(name, is_dir), ...]."""
    p = project_root / path if path != "." else project_root
    p = p.resolve()
    if not p.exists() or not p.is_dir():
        return []
    out = []
    for child in sorted(p.iterdir()):
        if not child.name.startswith("."):
            out.append((child.name, child.is_dir()))
    return out


def write_file(project_root: Path, path: str, content: str) -> None:
    """Create or overwrite file."""
    p = project_root / path if not Path(path).is_absolute() else Path(path)
    p = p.resolve()
    proot = project_root.resolve()
    if not str(p).startswith(str(proot)):
        raise ValueError(f"Path outside project: {path}")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def edit_file(project_root: Path, path: str, old: str, new: str, replace_all: bool = False) -> str | None:
    """
    Apply search-replace. Tries hard to match (whitespace normalization).
    Returns error message if failed, else None.
    """
    content = read_file(project_root, path)
    if not old.strip():
        if Path(project_root / path).exists():
            return "Cannot create file: already exists"
        write_file(project_root, path, new)
        return None

    # Find matches
    content_norm = _normalize_whitespace(content)
    old_norm = _normalize_whitespace(old)
    old_lines = old.strip().split("\n")
    content_lines = content.split("\n")

    matches = []
    for i in range(len(content_lines) - len(old_lines) + 1):
        window = "\n".join(content_lines[i : i + len(old_lines)])
        if _normalize_whitespace(window) == old_norm:
            matches.append(i)

    if not matches:
        return f"old_string not found in {path}"

    if len(matches) > 1 and not replace_all:
        return f"Multiple matches ({len(matches)}) for old_string; use replace_all"

    # Replace: for multiple with replace_all, do from bottom to top to preserve indices
    for i in reversed(matches):
        before = content_lines[:i]
        after = content_lines[i + len(old_lines) :]
        new_lines = new.rstrip().split("\n") if new.rstrip() else [""]
        content_lines = before + new_lines + after

    result = "\n".join(content_lines)
    write_file(project_root, path, result)
    return None
