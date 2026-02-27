"""Context accumulation for the agent."""

from dataclasses import dataclass, field
from pathlib import Path

from executor import read_file, grep, list_dir, read_header_for_api, ReadFileRequest, GrepRequest, ListDirRequest, ApiOverviewRequest


@dataclass
class Context:
    """Accumulated context: files, search results, lint/compile output."""

    files: dict[str, str] = field(default_factory=dict)  # path -> content
    api_overviews: dict[str, str] = field(default_factory=dict)  # header -> content
    searches: list[tuple[str, str, list[tuple[str, int, str]]]] = field(default_factory=list)  # (pattern, path, matches)
    dirs: list[tuple[str, list[tuple[str, bool]]]] = field(default_factory=list)  # (path, entries)
    lint_output: str = ""
    compile_output: str = ""
    edit_failures: list[tuple[str, str]] = field(default_factory=list)  # (path, reason)

    def add_file(self, path: str, content: str) -> None:
        self.files[path] = content

    def add_api_overview(self, header: str, content: str) -> None:
        self.api_overviews[header] = content

    def add_search(self, pattern: str, path: str, matches: list[tuple[str, int, str]]) -> None:
        self.searches.append((pattern, path, matches))

    def add_dir(self, path: str, entries: list[tuple[str, bool]]) -> None:
        self.dirs.append((path, entries))

    def set_lint(self, output: str) -> None:
        self.lint_output = output

    def set_compile(self, output: str) -> None:
        self.compile_output = output

    def add_edit_failure(self, path: str, reason: str) -> None:
        self.edit_failures.append((path, reason))

    def to_xml(self, project_root: Path) -> str:
        """Render context as XML for the prompt."""
        parts = ["<context>"]

        if self.files:
            parts.append("  <files>")
            for path, content in self.files.items():
                escaped = content.replace("]]>", "]]]]><![CDATA[>")
                parts.append(f'    <file path="{path}">')
                parts.append(f"      <content><![CDATA[\n{content}\n]]></content>")
                parts.append("    </file>")
            parts.append("  </files>")

        if self.api_overviews:
            parts.append("  <api_overviews>")
            for header, content in self.api_overviews.items():
                escaped = content.replace("]]>", "]]]]><![CDATA[>")
                parts.append(f'    <api_overview header="{_escape(header)}">')
                parts.append(f"<![CDATA[\n{content}\n]]>")
                parts.append("    </api_overview>")
            parts.append("  </api_overviews>")

        if self.searches:
            for pattern, path, matches in self.searches:
                parts.append(f'  <search pattern="{_escape(pattern)}" path="{_escape(path)}">')
                for fpath, line_num, line in matches[:50]:  # limit
                    parts.append(f'    <match file="{_escape(fpath)}" line="{line_num}">{_escape(line)}</match>')
                if len(matches) > 50:
                    parts.append(f"    <!-- {len(matches) - 50} more matches -->")
                parts.append("  </search>")

        if self.dirs:
            for path, entries in self.dirs:
                parts.append(f'  <list_dir path="{_escape(path)}">')
                for name, is_dir in entries[:100]:
                    tag = "dir" if is_dir else "file"
                    parts.append(f'    <{tag} name="{_escape(name)}" />')
                if len(entries) > 100:
                    parts.append(f"    <!-- {len(entries) - 100} more -->")
                parts.append("  </list_dir>")

        if self.lint_output:
            escaped = self.lint_output.replace("]]>", "]]]]><![CDATA[>")
            parts.append("  <lint_errors>")
            parts.append(f"<![CDATA[\n{escaped}\n]]>")
            parts.append("  </lint_errors>")

        if self.compile_output:
            escaped = self.compile_output.replace("]]>", "]]]]><![CDATA[>")
            parts.append("  <compile_output>")
            parts.append(f"<![CDATA[\n{escaped}\n]]>")
            parts.append("  </compile_output>")

        if self.edit_failures:
            parts.append("  <edit_failures>")
            for path, reason in self.edit_failures:
                parts.append(f'    <failure path="{_escape(path)}" reason="{_escape(reason)}" />')
            parts.append("  </edit_failures>")

        parts.append("</context>")
        return "\n".join(parts)


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def fulfill_requests(
    project_root: Path,
    context: Context,
    requests: list[ReadFileRequest | GrepRequest | ListDirRequest | ApiOverviewRequest],
    idf_path: Path | None = None,
) -> None:
    """Fulfill context requests and add results to context."""
    for req in requests:
        if isinstance(req, ReadFileRequest):
            try:
                content = read_file(project_root, req.path)
                context.add_file(req.path, content)
            except Exception as e:
                context.add_file(req.path, f"(error reading: {e})")
        elif isinstance(req, GrepRequest):
            matches = grep(project_root, req.pattern, req.path)
            context.add_search(req.pattern, req.path, matches)
        elif isinstance(req, ListDirRequest):
            entries = list_dir(project_root, req.path)
            context.add_dir(req.path, entries)
        elif isinstance(req, ApiOverviewRequest):
            content = read_header_for_api(project_root, req.header, idf_path)
            context.add_api_overview(req.header, content)
