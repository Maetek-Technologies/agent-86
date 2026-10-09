"""Discover a hosted model's real context window from OpenRouter's ``/models`` endpoint.

The name table in :mod:`agent86.cognitive.capabilities` guesses from substrings, which is wrong
for hosted models (``openrouter:qwen/qwen3.7-max`` matched the generic ``qwen`` row: 32,768).
OpenRouter reports ``context_length`` per model, so ask it -- memoized per process, cached on
disk for 24h, with a short timeout. Every failure returns ``None`` so the caller falls through
to the old behaviour. Stdlib only at import time; httpx lives behind ``catalog`` (lazy).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:  # pragma: no cover - typing only
    from agent86.config import Config, ProviderConfig

CACHE_TTL_S = 24 * 3600
_FETCH_TIMEOUT_S = 3.0
_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

#: normalized base_url -> {lowercased model id: context_length}. `{}` is a negative memo.
_MEMO: dict[str, dict[str, int]] = {}


def clear_memo() -> None:
    _MEMO.clear()


def _cache_path() -> Path:
    from agent86.config import USER_CONFIG_DIR

    return USER_CONFIG_DIR / "cache" / "model_context_windows.json"


def _normalize(base_url: str) -> str:
    return base_url.strip().rstrip("/")


def is_openrouter(provider: str, pconf: ProviderConfig | None) -> bool:
    """True for the ``openrouter`` section or any section whose host is on openrouter.ai."""
    try:
        if provider == "openrouter":
            return True
        host = urlparse(pconf.base_url or "").hostname if pconf else None
        return bool(host) and (host == "openrouter.ai" or str(host).endswith(".openrouter.ai"))
    except Exception:  # noqa: BLE001
        return False


def _fetch_context_lengths(base_url: str, api_key: str | None) -> dict[str, int]:
    from agent86.cognitive.catalog import fetch_openai_compatible_context_lengths

    return fetch_openai_compatible_context_lengths(base_url, api_key, timeout=_FETCH_TIMEOUT_S)


def _read_entry(base_url: str) -> tuple[float, dict[str, int]] | None:
    try:
        raw: Any = json.loads(_cache_path().read_text(encoding="utf-8"))
        entry = raw[base_url]
        fetched_at = float(entry["fetched_at"])
        models = {
            str(k): int(v)
            for k, v in entry["models"].items()
            if isinstance(v, int) and not isinstance(v, bool) and v > 0
        }
        return fetched_at, models
    except Exception:  # noqa: BLE001 - absent/corrupt cache is simply a miss
        return None


def _write_entry(base_url: str, models: dict[str, int]) -> None:
    try:
        path = _cache_path()
        try:
            existing: Any = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                existing = {}
        except Exception:  # noqa: BLE001
            existing = {}
        existing[base_url] = {"fetched_at": time.time(), "models": models}
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(existing), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def _load_models(base_url: str, provider: str, pconf: ProviderConfig | None) -> dict[str, int]:
    if base_url in _MEMO:
        return _MEMO[base_url]
    cached = _read_entry(base_url)
    if cached and time.time() - cached[0] < CACHE_TTL_S and cached[1]:
        _MEMO[base_url] = cached[1]
        return cached[1]
    try:
        from agent86.secrets import resolve_api_key

        key = resolve_api_key(provider, pconf.api_key_env if pconf else None)
        models = _fetch_context_lengths(base_url, key)
        if models:
            _write_entry(base_url, models)
            _MEMO[base_url] = models
            return models
    except Exception:  # noqa: BLE001 - offline, HTTP error, bad JSON: all the same
        pass
    result = cached[1] if cached else {}
    _MEMO[base_url] = result
    return result


def openrouter_context_window(provider: str, model: str, config: Config) -> int | None:
    """OpenRouter-reported context window for ``model``, or ``None`` (never raises)."""
    try:
        pconf = config.providers.get(provider)
        if not is_openrouter(provider, pconf):
            return None
        base_url = _normalize(pconf.base_url if pconf and pconf.base_url else _DEFAULT_BASE_URL)
        value = _load_models(base_url, provider, pconf).get(model.strip().lower())
        return int(value) if value and value > 0 else None
    except Exception:  # noqa: BLE001
        return None


__all__ = ["clear_memo", "is_openrouter", "openrouter_context_window"]
