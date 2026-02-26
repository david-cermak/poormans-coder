# poormans-coder

Minimal agentic coder that works with distilled/small LLMs. Uses XML tags instead of tool schemas—no function calling required.

**Flow:** Task → LLM outputs XML (write_file, edit_file, need_context) → we execute → lint → repeat.

**Run:**
```bash
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python main.py --prompt "Implement bubble sort and compare with sorted()"
```

Uses OpenAI-compatible API (OpenAI or local Ollama). See `config.yaml`.
