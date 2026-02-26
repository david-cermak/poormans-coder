"""Build prompts for the LLM."""

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
