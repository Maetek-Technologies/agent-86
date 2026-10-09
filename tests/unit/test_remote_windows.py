"""OpenRouter context-window discovery: fetch parsing, memo, disk cache, fallbacks."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

import agent86.cognitive.catalog as catalog
import agent86.cognitive.remote_windows as rw
from agent86.cognitive.capabilities import context_window_for
from agent86.config import ProviderConfig, load_config

FIXTURE = Path(__file__).parent.parent / "fixtures" / "catalog" / "openrouter_models.json"
BASE = "https://openrouter.ai/api/v1"
REF = "openrouter:qwen/qwen3.7-max"


class Fetcher:
    def __init__(self, result=None, exc=None):
        self.result = result if result is not None else {"qwen/qwen3.7-max": 262144}
        self.exc = exc
        self.calls: list[tuple[str, str | None]] = []

    def __call__(self, base_url, api_key):
        self.calls.append((base_url, api_key))
        if self.exc:
            raise self.exc
        return self.result


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def fetcher(monkeypatch):
    f = Fetcher()
    monkeypatch.setattr(rw, "_fetch_context_lengths", f)
    return f


def test_fetch_context_lengths_filters_invalid(monkeypatch):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["data"] += [
        {"id": "no/ctx"},
        {"id": "str/ctx", "context_length": "100"},
        {"id": "zero/ctx", "context_length": 0},
        {"id": "neg/ctx", "context_length": -5},
        {"id": "Mixed/Case", "context_length": 4096},
        "not-a-dict",
    ]
    monkeypatch.setattr(catalog, "_get_json", lambda url, headers, timeout=0: data)
    out = catalog.fetch_openai_compatible_context_lengths(BASE, None)
    assert out["anthropic/claude-3.7-sonnet"] == 200000
    assert out["mixed/case"] == 4096
    assert not {"no/ctx", "str/ctx", "zero/ctx", "neg/ctx"} & set(out)
    assert all(isinstance(v, int) and v > 0 for v in out.values())


def test_discovered_beats_table(cfg, fetcher):
    assert context_window_for(REF, cfg) == 262144


def test_override_wins_and_skips_fetch(cfg, fetcher):
    cfg.model.context_window = {REF: 50000}
    assert context_window_for(REF, cfg) == 50000
    assert fetcher.calls == []


def test_host_detection(cfg, fetcher):
    cfg.providers["myor"] = ProviderConfig(base_url=BASE)
    assert context_window_for("myor:qwen/qwen3.7-max", cfg) == 262144
    fetcher.calls.clear()
    rw.clear_memo()
    context_window_for("groq:llama-3.3-70b", cfg)
    assert fetcher.calls == []


@pytest.mark.parametrize("exc", [OSError("x"), ValueError("x")])
def test_failure_falls_back(cfg, monkeypatch, exc):
    monkeypatch.setattr(rw, "_fetch_context_lengths", Fetcher(exc=exc))
    assert context_window_for(REF, cfg) == 32_768


def test_catalog_unavailable_falls_back(cfg, monkeypatch):
    monkeypatch.setattr(
        rw, "_fetch_context_lengths", Fetcher(exc=catalog.CatalogUnavailable("down"))
    )
    assert context_window_for(REF, cfg) == 32_768


def test_model_absent_falls_back(cfg, fetcher):
    assert context_window_for("openrouter:qwen/other", cfg) == 32_768


def test_memo_and_negative_memo(cfg, fetcher, monkeypatch):
    context_window_for(REF, cfg)
    context_window_for(REF, cfg)
    assert len(fetcher.calls) == 1
    rw.clear_memo()
    rw._cache_path().unlink()
    bad = Fetcher(exc=OSError("x"))
    monkeypatch.setattr(rw, "_fetch_context_lengths", bad)
    context_window_for(REF, cfg)
    context_window_for(REF, cfg)
    assert len(bad.calls) == 1


def _write_cache(age_s, models):
    rw._cache_path().write_text(
        json.dumps({BASE: {"fetched_at": time.time() - age_s, "models": models}}),
        encoding="utf-8",
    )


def test_fresh_cache_means_no_fetch(cfg, fetcher):
    _write_cache(60, {"qwen/qwen3.7-max": 111111})
    assert context_window_for(REF, cfg) == 111111
    assert fetcher.calls == []


def test_stale_cache_refetches_and_rewrites(cfg, fetcher):
    _write_cache(25 * 3600, {"qwen/qwen3.7-max": 111111})
    assert context_window_for(REF, cfg) == 262144
    assert len(fetcher.calls) == 1
    saved = json.loads(rw._cache_path().read_text(encoding="utf-8"))
    assert saved[BASE]["models"]["qwen/qwen3.7-max"] == 262144


def test_stale_cache_used_on_failure(cfg, monkeypatch):
    _write_cache(25 * 3600, {"qwen/qwen3.7-max": 111111})
    monkeypatch.setattr(rw, "_fetch_context_lengths", Fetcher(exc=OSError("x")))
    assert context_window_for(REF, cfg) == 111111


def test_corrupt_cache_ignored(cfg, fetcher):
    rw._cache_path().write_text("{not json", encoding="utf-8")
    assert context_window_for(REF, cfg) == 262144


def test_key_is_passed_but_never_cached(cfg, fetcher, monkeypatch):
    import agent86.secrets as secrets

    key = "sk-or-test-key-1234567890"
    monkeypatch.setattr(secrets, "resolve_api_key", lambda p, env: key)
    context_window_for(REF, cfg)
    assert fetcher.calls[0][1] == key
    assert key not in rw._cache_path().read_text(encoding="utf-8")


def test_no_key_still_fetches(cfg, fetcher, monkeypatch):
    import agent86.secrets as secrets

    monkeypatch.setattr(secrets, "resolve_api_key", lambda p, env: None)
    assert context_window_for(REF, cfg) == 262144
    assert fetcher.calls[0][1] is None
