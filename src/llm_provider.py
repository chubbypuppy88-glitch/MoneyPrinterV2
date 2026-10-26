"""Ollama text requests with finite output and network-wait limits."""
import time

import httpx
import ollama

from config import get_ollama_base_url

_selected_model: str | None = None
REQUEST_TIMEOUT_SECONDS = 120.0
MAX_OUTPUT_TOKENS = 512


def _client() -> ollama.Client:
    # Ollama's Python client otherwise defaults to no timeout. This is an
    # inactivity timeout, not a guaranteed wall-clock deadline for the video.
    return ollama.Client(
        host=get_ollama_base_url(),
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=10.0),
    )


def _close_client(client) -> None:
    # Client.close is public in current ollama-python; tolerate older releases.
    close = getattr(client, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass


def list_models() -> list[str]:
    """Return sorted model names without an unbounded network wait."""
    client = _client()
    try:
        response = client.list()
        return sorted(m.model for m in response.models)
    finally:
        _close_client(client)


def select_model(model: str) -> None:
    """Select an already-downloaded model; this does not contact Ollama."""
    global _selected_model
    _selected_model = model


def get_active_model() -> str | None:
    return _selected_model


def generate_text(prompt: str, model_name: str = None) -> str:
    """Generate bounded text, without printing prompts or provider error bodies."""
    model = model_name or _selected_model
    if not model:
        raise RuntimeError(
            "No Ollama model selected. Call select_model() first or pass model_name."
        )

    print(
        f"[TEXT] Waiting for Ollama: at most {MAX_OUTPUT_TOKENS} output tokens; "
        f"{int(REQUEST_TIMEOUT_SECONDS)}s network inactivity limit.", flush=True,
    )
    started = time.monotonic()
    client = _client()
    try:
        response = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            options={"num_predict": MAX_OUTPUT_TOKENS},
        )
        content = response["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            print("[TEXT] Ollama returned no usable text.", flush=True)
            raise RuntimeError("Ollama returned no usable text.")
        print(f"[TEXT] Ollama response received in {time.monotonic() - started:.1f}s.", flush=True)
        return content.strip()
    except httpx.TimeoutException:
        print("[TEXT] Ollama timed out. No automatic retry or model download.", flush=True)
        raise TimeoutError("Ollama text request timed out.") from None
    finally:
        _close_client(client)
