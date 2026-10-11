"""A small language-model client for wording notes (used by AI Insight). It only needs a callable (system, user) -> text.

Provider, from environment variables (a key is never written to a file or printed):
  ANTHROPIC_API_KEY (+ optional LLM_MODEL, default claude-haiku-4-5-20251001)   Anthropic Messages API
  LLM_BASE_URL (+ LLM_MODEL, optional LLM_API_KEY)                                any OpenAI-compatible server: vLLM on the AMD GPU, or a hosted one
  OPENAI_API_KEY (+ LLM_MODEL, optional LLM_BASE_URL)                             OpenAI-compatible hosted API
  LLM_PROVIDER=anthropic|openai forces the choice. With none of these set, `from_env()` returns None and AI Insight uses its templates.
"""
import json
import os
import urllib.request

DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


def _post(url: str, headers: dict, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def anthropic(api_key: str, model: str = None, timeout: float = 20.0):
    model = model or DEFAULT_ANTHROPIC_MODEL

    def call(system: str, user: str) -> str:
        out = _post("https://api.anthropic.com/v1/messages", {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                    {"model": model, "max_tokens": 160, "temperature": 0.2, "system": system,
                     "messages": [{"role": "user", "content": user}]}, timeout)
        return "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text").strip()
    return call


def openai_compatible(base_url: str, api_key: str = None, model: str = None, timeout: float = 20.0):
    model = model or DEFAULT_OPENAI_MODEL
    base = base_url.rstrip("/")
    url = base + ("/chat/completions" if base.endswith("/v1") else "/v1/chat/completions")

    def call(system: str, user: str) -> str:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        out = _post(url, headers, {"model": model, "max_tokens": 160, "temperature": 0.2,
                                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}, timeout)
        return out["choices"][0]["message"]["content"].strip()
    return call


def from_env(env=None):
    env = os.environ if env is None else env
    provider = (env.get("LLM_PROVIDER") or "").lower()
    model = env.get("LLM_MODEL")
    if provider == "anthropic" or (not provider and env.get("ANTHROPIC_API_KEY")):
        key = env.get("ANTHROPIC_API_KEY")
        return anthropic(key, model) if key else None
    base = env.get("LLM_BASE_URL")
    if provider == "openai" or base or env.get("OPENAI_API_KEY"):
        return openai_compatible(base or "https://api.openai.com/v1", env.get("LLM_API_KEY") or env.get("OPENAI_API_KEY"), model)
    return None


def describe(env=None) -> str:
    env = os.environ if env is None else env
    if from_env(env) is None:
        return "no language model configured: standard wording"
    if (env.get("LLM_PROVIDER") or "").lower() == "anthropic" or (not env.get("LLM_PROVIDER") and env.get("ANTHROPIC_API_KEY")):
        return f"Anthropic API ({env.get('LLM_MODEL') or DEFAULT_ANTHROPIC_MODEL})"
    return f"OpenAI-compatible API ({env.get('LLM_BASE_URL') or 'api.openai.com'}, {env.get('LLM_MODEL') or DEFAULT_OPENAI_MODEL})"
