#!/usr/bin/env python3
"""poormans-coder: minimal agentic coder for distilled LLMs."""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from config import Config
from context import Context, fulfill_requests
from executor import write_file, edit_file, read_file
from lint import run_command
from llm import create_client, generate
from parser import parse_output
from prompt import build_user_message, extract_at_mentions

# Setup logging
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def build_turn_summary(parsed, lint_out: str | None, compile_out: str | None) -> str:
    """Build short summary of what happened this turn."""
    parts = []
    if parsed.write_files:
        files = ", ".join(w.path for w in parsed.write_files)
        parts.append(f"Wrote: {files}")
    if parsed.edit_files:
        files = ", ".join(e.path for e in parsed.edit_files)
        parts.append(f"Edited: {files}")
    if parsed.done:
        parts.append("Done.")
    if lint_out and "error" in lint_out.lower() or (lint_out and lint_out.strip() and "All checks passed" not in lint_out):
        parts.append(f"Lint: {lint_out[:200]}...")
    elif lint_out:
        parts.append("Lint: passed")
    if compile_out and compile_out.strip():
        parts.append(f"Compile: {compile_out[:200]}...")
    return " ".join(parts) if parts else "No changes."


def run_agent(config: Config, task: str, project_root: Path, cwd: Path, verbose: bool = False) -> None:
    """Main agent loop."""
    client = create_client(config.llm.api_key, config.llm.base_url)
    context = Context()

    # Pre-load @path/to/file mentions from task into context
    for path in extract_at_mentions(task, cwd, project_root):
        try:
            content = read_file(project_root, path)
            context.add_file(path, content)
            log.info("Pre-loaded @%s", path)
        except Exception as e:
            log.warning("Could not pre-load @%s: %s", path, e)

    turn_summary = ""

    for turn in range(config.max_turns):
        log.info("Turn %d", turn + 1)

        user_content = build_user_message(
            task=task,
            turn_summary=turn_summary,
            context_xml=context.to_xml(project_root),
        )

        messages = [
            {"role": "system", "content": config.system_prompt},
            {"role": "user", "content": user_content},
        ]

        if verbose:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write("\n\n=== LLM REQUEST ===\n")
                f.write("--- system ---\n")
                f.write(config.system_prompt)
                f.write("\n--- user ---\n")
                f.write(user_content)
                f.write("\n")

        try:
            response = generate(
                client,
                model=config.llm.model,
                messages=messages,
                stream=config.llm.stream,
            )
        except Exception as e:
            log.error("LLM error: %s", e)
            raise

        if verbose:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write("\n=== LLM RESPONSE ===\n")
                f.write(response)
                f.write("\n")

        try:
            parsed = parse_output(response)
        except ValueError as e:
            log.error("Parse error: %s", e)
            raise

        # 1. Fulfill context requests
        if parsed.need_context:
            idf_path = config.resolve_idf_path(project_root)
            fulfill_requests(project_root, context, parsed.need_context, idf_path=idf_path)

        # 2. Apply file operations
        context.edit_failures.clear()
        for w in parsed.write_files:
            try:
                write_file(project_root, w.path, w.content)
                context.add_file(w.path, w.content)
                log.info("Wrote %s", w.path)
            except Exception as e:
                log.error("Write failed %s: %s", w.path, e)
                context.add_edit_failure(w.path, str(e))

        for e in parsed.edit_files:
            err = edit_file(project_root, e.path, e.old, e.new, e.replace_all)
            if err:
                log.warning("Edit failed %s: %s", e.path, err)
                context.add_edit_failure(e.path, err)
            else:
                try:
                    context.add_file(e.path, read_file(project_root, e.path))
                except Exception:
                    pass
                log.info("Edited %s", e.path)

        # 3. Check for done
        if parsed.done:
            log.info("Model signaled done: %s", parsed.done_message)
            break

        # 4. Run lint/compile
        lint_out = None
        compile_out = None
        if config.lint.enabled:
            lint_cwd = project_root / config.lint.cwd if config.lint.cwd != "." else project_root
            lint_out = run_command(lint_cwd, config.lint.command)
            context.set_lint(lint_out)
        if config.compile.enabled:
            compile_cwd = project_root / config.compile.cwd if config.compile.cwd != "." else project_root
            compile_out = run_command(compile_cwd, config.compile.command)
            context.set_compile(compile_out)

        # 5. Build turn summary
        turn_summary = build_turn_summary(parsed, lint_out, compile_out)
        log.info("Turn summary: %s", turn_summary)

    log.info("Agent finished. Log: %s", LOG_FILE)


def main():
    parser = argparse.ArgumentParser(description="poormans-coder: minimal agentic coder")
    parser.add_argument("--prompt", "-p", required=True, help="Task to accomplish")
    parser.add_argument("--config", "-c", default=None, help="Config YAML path")
    parser.add_argument("--project", default=None, help="Project root (overrides config)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Log full LLM request/response to log file")
    args = parser.parse_args()

    base = Path(__file__).parent
    config_path = Path(args.config) if args.config else base / "config.yaml"
    config = Config.load(config_path)

    cwd = Path.cwd()
    project_root = Path(args.project) if args.project else config.resolve_project_root(cwd)
    project_root = project_root.resolve()

    log.info("Project root: %s", project_root)
    run_agent(config, args.prompt, project_root, cwd, verbose=args.verbose)


if __name__ == "__main__":
    main()
