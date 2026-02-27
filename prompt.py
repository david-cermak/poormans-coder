"""Build prompts for the LLM."""

import re
from pathlib import Path


def extract_at_mentions(task: str, cwd: Path, project_root: Path) -> list[str]:
    """Extract @path/to/file from task; return project_root-relative paths that exist."""
    # Match @path (alphanumeric, /, _, -, .)
    pattern = re.compile(r"@([a-zA-Z0-9_./\-]+)")
    seen = set()
    result = []
    proot = project_root.resolve()
    proot_name = proot.name

    for m in pattern.finditer(task):
        raw = m.group(1).strip()
        if not raw or raw in seen:
            continue
        seen.add(raw)

        # Try cwd first (e.g. @test/proto/... from repo root)
        full = (cwd / raw).resolve()
        if full.is_file():
            # If path starts with project_root name (e.g. test/), use the rest as project-rel
            if raw.startswith(proot_name + "/"):
                result.append(raw[len(proot_name) + 1 :])
            else:
                try:
                    rel = full.relative_to(proot)
                    result.append(str(rel))
                except ValueError:
                    # full is outside project (e.g. via symlink); try project_root/raw
                    p = (proot / raw).resolve()
                    if p.is_file():
                        result.append(raw)
        else:
            # Try relative to project_root
            p = (proot / raw).resolve()
            if p.is_file():
                try:
                    rel = p.relative_to(proot)
                    result.append(str(rel))
                except ValueError:
                    result.append(raw)
    return result


OUTPUT_FORMAT = """
<output_format>
To create a new file:
  <write_file path="/path/to/file.py">
  content here
  </write_file>

To edit an existing file:
  <edit_file path="/path/to/file.py">
    <old>exact text to replace</old>
    <new>replacement text</new>
  </edit_file>

To request more context:
  <need_context>
    <read_file path="/path/to/file.py" />
    <grep pattern="pattern" path="." />
    <list_dir path="." />
    <api_overview header="esp_log.h" />
  </need_context>

When done:
  <done>optional summary</done>
</output_format>
"""


def build_user_message(
    task: str,
    turn_summary: str,
    context_xml: str,
    output_format: str = OUTPUT_FORMAT,
) -> str:
    """Build the user message for a turn."""
    parts = []

    parts.append("## Task\n")
    parts.append(task.strip())
    parts.append("\n")

    if turn_summary:
        parts.append("## Previous turn\n")
        parts.append(turn_summary.strip())
        parts.append("\n\n")

    if context_xml.strip():
        parts.append("## Context\n")
        parts.append(context_xml)
        parts.append("\n\n")

    parts.append("## Your response\n")
    parts.append("Output your actions as XML using the format below.\n")
    parts.append(output_format)

    return "".join(parts)
