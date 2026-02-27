"""Load and validate configuration."""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class LLMConfig:
    model: str
    base_url: str | None
    api_key: str
    stream: bool = True


@dataclass
class LintConfig:
    enabled: bool
    command: str
    cwd: str


@dataclass
class Config:
    llm: LLMConfig
    project_root: str
    idf_path: str | None
    max_turns: int
    lint: LintConfig
    compile: LintConfig  # same shape as lint
    system_prompt: str

    @classmethod
    def load(cls, config_path: Path, system_prompt_path: Path | None = None) -> "Config":
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

        llm = data.get("llm", {})
        llm_config = LLMConfig(
            model=llm.get("model", "gpt-4o-mini"),
            base_url=llm.get("base_url"),
            api_key=llm.get("api_key", "ollama"),
            stream=llm.get("stream", True),
        )

        lint_data = data.get("lint", {})
        lint_config = LintConfig(
            enabled=lint_data.get("enabled", False),
            command=lint_data.get("command", "ruff check ."),
            cwd=lint_data.get("cwd", "."),
        )

        compile_data = data.get("compile", {})
        compile_config = LintConfig(
            enabled=compile_data.get("enabled", False),
            command=compile_data.get("command", "python -m py_compile ."),
            cwd=compile_data.get("cwd", "."),
        )

        system_path = system_prompt_path or config_path.parent / "system.md"
        system_prompt = system_path.read_text() if system_path.exists() else ""

        idf_path = data.get("idf_path")
        if idf_path and not Path(idf_path).is_absolute():
            idf_path = str((Path(config_path).parent / idf_path).resolve())

        return cls(
            llm=llm_config,
            project_root=data.get("project_root", "."),
            idf_path=idf_path,
            max_turns=data.get("max_turns", 10),
            lint=lint_config,
            compile=compile_config,
            system_prompt=system_prompt,
        )

    def resolve_project_root(self, cwd: Path) -> Path:
        root = Path(self.project_root)
        if not root.is_absolute():
            root = (cwd / root).resolve()
        return root

    def resolve_idf_path(self, cwd: Path) -> Path | None:
        if not self.idf_path:
            return None
        p = Path(self.idf_path)
        if not p.is_absolute():
            p = (cwd / self.idf_path).resolve()
        return p if p.exists() else None
