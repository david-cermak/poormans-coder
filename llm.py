"""LLM client - OpenAI-compatible API (OpenAI + Ollama)."""

from openai import OpenAI


def create_client(api_key: str, base_url: str | None) -> OpenAI:
    """Create OpenAI client. For Ollama, use base_url='http://localhost:11434/v1'."""
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def generate(
    client: OpenAI,
    model: str,
    messages: list[dict],
    stream: bool = True,
) -> str:
    """Generate completion. If stream=True, collect chunks and return full text."""
    stream_obj = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=stream,
    )

    if stream:
        chunks = []
        for chunk in stream_obj:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                chunks.append(content)
                print(content, end="", flush=True)
        print()
        return "".join(chunks)
    else:
        return stream_obj.choices[0].message.content or ""
