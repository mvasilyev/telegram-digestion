import logging

import httpx

from app.db import repository as repo
from app.config import settings

log = logging.getLogger(__name__)


async def _get_llm_setting(key: str, default: str) -> str:
    val = await repo.get_setting(key)
    return val if val else default


async def get_llm_config() -> dict:
    return {
        "base_url": await _get_llm_setting("llm_base_url", settings.llm_base_url),
        "model": await _get_llm_setting("llm_model", settings.llm_model),
        "api_key": await _get_llm_setting("llm_api_key", settings.llm_api_key),
    }


async def chat_completion(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> dict:
    """Call OpenAI-compatible /chat/completions endpoint.
    Returns {"content": str, "prompt_tokens": int, "completion_tokens": int}.
    """
    cfg = await get_llm_config()
    url = f"{cfg['base_url'].rstrip('/')}/chat/completions"

    headers = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        headers["Authorization"] = f"Bearer {cfg['api_key']}"

    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    timeout = httpx.Timeout(connect=10, read=300, write=10, pool=10)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    usage = data.get("usage", {})
    return {
        "content": data["choices"][0]["message"]["content"],
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
    }


async def check_llm_health() -> bool:
    """Quick health check — try to list models."""
    try:
        cfg = await get_llm_config()
        url = f"{cfg['base_url'].rstrip('/')}/models"
        headers = {}
        if cfg["api_key"]:
            headers["Authorization"] = f"Bearer {cfg['api_key']}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
            return resp.status_code == 200
    except Exception:
        return False
