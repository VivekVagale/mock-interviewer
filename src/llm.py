"""Tiny client for a local Ollama server. No API key, nothing leaves the laptop."""

import json
import os

import requests

HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")


def chat(messages: list[dict], model: str = MODEL, schema: dict | None = None,
         temperature: float = 0.0, timeout: int = 300) -> str:
    """Send a chat to Ollama and return the reply text.

    `schema` turns on Ollama's structured output: the model is forced to return
    JSON matching the schema, so the grader's reply can always be parsed.
    `num_predict` caps the reply length: small models in JSON mode sometimes
    never stop generating, and a cap turns a hang into a fast, visible error.
    `think=False` turns off the hidden reasoning some models (qwen3) do, which
    is slower and not needed for short answers.
    """
    body = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"temperature": temperature, "num_ctx": 4096, "num_predict": 1200},
    }
    if schema:
        body["format"] = schema
    r = requests.post(f"{HOST}/api/chat", json=body, timeout=timeout)
    r.raise_for_status()
    return r.json()["message"]["content"]


def chat_json(messages: list[dict], schema: dict, **kw) -> dict:
    return json.loads(chat(messages, schema=schema, **kw))


def is_up() -> bool:
    try:
        return requests.get(f"{HOST}/api/tags", timeout=3).ok
    except requests.RequestException:
        return False


def installed_models() -> list[str]:
    try:
        return [m["name"] for m in requests.get(f"{HOST}/api/tags", timeout=3).json()["models"]]
    except requests.RequestException:
        return []
