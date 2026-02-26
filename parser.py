"""Parse LLM XML output into structured actions."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from defusedxml import ElementTree as DefusedET

from executor import ReadFileRequest, GrepRequest, ListDirRequest, WriteFileOp, EditFileOp


@dataclass
class ParsedOutput:
    write_files: list[WriteFileOp] = field(default_factory=list)
    edit_files: list[EditFileOp] = field(default_factory=list)
    need_context: list[ReadFileRequest | GrepRequest | ListDirRequest] = field(default_factory=list)
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


def parse_output(response: str) -> ParsedOutput:
    """Parse LLM response into structured actions. Fast-fail on parse error."""
    block = _extract_xml_block(response)
    if not block:
        raise ValueError("No XML found in response")

    wrapped = f"<root>{block}</root>"
    try:
        root = DefusedET.fromstring(wrapped)
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML: {e}") from e

    out = ParsedOutput()

    for elem in root.iter():
        tag = elem.tag
        if tag == "write_file":
            path = elem.get("path", "").strip()
            content = _elem_text(elem)
            out.write_files.append(WriteFileOp(path=path, content=content))
        elif tag == "edit_file":
            path = elem.get("path", "").strip()
            old_elem = elem.find("old")
            new_elem = elem.find("new")
            old_str = _elem_text(old_elem)
            new_str = _elem_text(new_elem)
            replace_all = elem.get("replace_all", "false").lower() == "true"
            out.edit_files.append(EditFileOp(path=path, old=old_str, new=new_str, replace_all=replace_all))
        elif tag == "need_context":
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
        elif tag == "done":
            out.done = True
            out.done_message = _elem_text(elem)

    return out
