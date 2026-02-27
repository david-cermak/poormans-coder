"""Parse LLM XML output into structured actions."""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from defusedxml import ElementTree as DefusedET

from executor import ReadFileRequest, GrepRequest, ListDirRequest, ApiOverviewRequest, WriteFileOp, EditFileOp


@dataclass
class ParsedOutput:
    write_files: list[WriteFileOp] = field(default_factory=list)
    edit_files: list[EditFileOp] = field(default_factory=list)
    need_context: list[ReadFileRequest | GrepRequest | ListDirRequest | ApiOverviewRequest] = field(default_factory=list)
    done: bool = False
    done_message: str = ""


def _extract_xml_block(text: str) -> str:
    """Extract XML from response - model might add prose before/after."""
    text = text.strip()
    start = text.find("<")
    end = text.rfind(">")
    if start == -1 or end == -1 or end <= start:
        return ""
    return text[start : end + 1]


def _elem_text(elem: ET.Element | None) -> str:
    """Get full text content of element."""
    if elem is None:
        return ""
    return "".join(elem.itertext())


def _extract_write_files_regex(block: str) -> list[WriteFileOp]:
    """Extract write_file blocks via regex so content with &, <, > doesn't break XML parse."""
    ops = []
    # Match <write_file path="...">content</write_file> - content can have any chars
    pat = re.compile(
        r'<write_file\s+path="([^"]*)"\s*>([\s\S]*?)</write_file>',
        re.IGNORECASE,
    )
    for m in pat.finditer(block):
        path, content = m.group(1).strip(), m.group(2)
        if path:
            ops.append(WriteFileOp(path=path, content=content))
    return ops


def _extract_edit_files_regex(block: str) -> list[EditFileOp]:
    """Extract edit_file blocks via regex so old/new content with &, <, > doesn't break XML parse."""
    ops = []
    # Match <edit_file path="..." replace_all="..."><old>...</old><new>...</new></edit_file>
    pat = re.compile(
        r'<edit_file\s+path="([^"]*)"([^>]*)>\s*<old>([\s\S]*?)</old>\s*<new>([\s\S]*?)</new>\s*</edit_file>',
        re.IGNORECASE,
    )
    for m in pat.finditer(block):
        path = m.group(1).strip()
        attrs = m.group(2)
        old_str = m.group(3)
        new_str = m.group(4)
        replace_all = re.search(r'replace_all\s*=\s*["\']true["\']', attrs, re.I) is not None
        if path:
            ops.append(EditFileOp(path=path, old=old_str, new=new_str, replace_all=replace_all))
    return ops


def _parse_need_context_and_done(block: str, out: ParsedOutput) -> None:
    """Parse need_context and done from block. Replace write_file/edit_file with placeholders to avoid XML errors."""
    # Replace write_file and edit_file blocks with inert placeholders so content doesn't break parse
    sanitized = re.sub(
        r'<write_file\s+path="[^"]*"\s*>[\s\S]*?</write_file>',
        '<_w/>',
        block,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r'<edit_file\s+path="[^"]*"[^>]*>\s*<old>[\s\S]*?</old>\s*<new>[\s\S]*?</new>\s*</edit_file>',
        '<_e/>',
        sanitized,
        flags=re.IGNORECASE,
    )
    wrapped = f"<root>{sanitized}</root>"
    try:
        root = DefusedET.fromstring(wrapped)
    except ET.ParseError:
        return  # need_context/done parsing is best-effort if block has other issues

    for elem in root.iter():
        tag = elem.tag
        if tag == "need_context":
            for child in elem:
                ctag = child.tag
                if ctag == "read_file":
                    p = child.get("path", "").strip()
                    out.need_context.append(ReadFileRequest(path=p))
                elif ctag == "grep":
                    pat = child.get("pattern", "").strip()
                    p = child.get("path", ".").strip()
                    out.need_context.append(GrepRequest(pattern=pat, path=p))
                elif ctag == "list_dir":
                    p = child.get("path", ".").strip()
                    out.need_context.append(ListDirRequest(path=p))
                elif ctag == "api_overview":
                    h = child.get("header", "").strip()
                    if h:
                        out.need_context.append(ApiOverviewRequest(header=h))
        elif tag == "done":
            out.done = True
            out.done_message = _elem_text(elem)


def parse_output(response: str) -> ParsedOutput:
    """Parse LLM response into structured actions. Uses regex for write_file/edit_file so content with &, <, > is OK."""
    block = _extract_xml_block(response)
    if not block:
        raise ValueError("No XML found in response")

    out = ParsedOutput()

    # Extract write_file and edit_file via regex (content may have &, <, > which break XML)
    out.write_files = _extract_write_files_regex(block)
    out.edit_files = _extract_edit_files_regex(block)

    # Parse need_context and done (after replacing heavy blocks with placeholders)
    _parse_need_context_and_done(block, out)

    return out
