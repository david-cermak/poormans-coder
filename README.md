# poormans-coder

Minimal agentic coder that works with distilled/small LLMs. Uses XML tags instead of tool schemas—no function calling required.

**Flow:** Task → LLM outputs XML (write_file, edit_file, need_context) → we execute → lint → repeat.

**Multi-turn:** The LLM can request context (files, grep, api_overview) first; the next turn receives it and implements. For C/ESP-IDF, use `<api_overview header="esp_log.h" />` when you need header API docs.

**Run:**
```bash
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python main.py --prompt "Implement bubble sort and compare with sorted()"
```

Use `@path/to/file` in the prompt to pre-load file content into context. Use `-v` / `--verbose` to log full LLM request/response to the log file.

**C/ESP-IDF:** Set `idf_path` in config.yaml (e.g. `/home/user/esp/idf`) so `api_overview` can resolve headers. Use `--project test` and configure lint/compile for your build.

Uses OpenAI-compatible API (OpenAI or local Ollama). See `config.yaml`.
