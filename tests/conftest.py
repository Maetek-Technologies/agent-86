"""Shared test fixtures."""

from __future__ import annotations

import pytest

import agent86.orchestration.loop as loop_mod
from agent86.observability.recorder import Recorder


@pytest.fixture(autouse=True)
def _no_home_writes(monkeypatch):
    """Keep the Harness from writing the flight recorder into the real ~/.agent86 in tests."""
    monkeypatch.setattr(loop_mod, "build_recorder", lambda config: Recorder(None))


@pytest.fixture(autouse=True)
def _no_remote_windows(monkeypatch, tmp_path):
    """Keep context-window discovery off the network and out of the real ~/.agent86."""
    import agent86.cognitive.remote_windows as rw

    def _offline(base_url, api_key):
        raise OSError("network disabled in tests")

    monkeypatch.setattr(rw, "_cache_path", lambda: tmp_path / "model_context_windows.json")
    monkeypatch.setattr(rw, "_fetch_context_lengths", _offline)
    rw.clear_memo()
    yield
    rw.clear_memo()
