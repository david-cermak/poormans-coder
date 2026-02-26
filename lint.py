"""Run lint and compile commands."""

import subprocess
from pathlib import Path


def run_command(cwd: Path, command: str) -> str:
    """Run command and return combined stdout+stderr."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        out = result.stdout or ""
        err = result.stderr or ""
        return (out + "\n" + err).strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out"
    except Exception as e:
        return str(e)
