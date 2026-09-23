"""Cross-document consistency for the Phase 10 MCP conformance audit.

Pins MCP-02 (one row per client-side spec capability), MCP-03 (each row records corpus
exercise), MCP-04 (every "out" ruling lands in ARCHITECTURE.md §15) and MCP-08..MCP-11 (four
ADRs, each stating a ruling). Pure file reads — no network, no `agent86` import.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# The documents do not exist until plans 10-03/10-04 land them. Remove this marker in plan 10-05.
pytestmark = pytest.mark.xfail(
    reason="Wave 0 scaffold - docs land in plans 10-03 and 10-04", strict=False
)

_ROOT = Path(__file__).resolve().parents[2]
_MATRIX = _ROOT / "docs" / "mcp-conformance-matrix.md"
_ARCH = _ROOT / "docs" / "ARCHITECTURE.md"
_ADR_DIR = _ROOT / "docs" / "adr"

#: One entry per client-side MCP spec capability, per 10-RESEARCH.md's spec-surface
#: enumeration pinned to protocol revision 2025-11-25. `server/discover` is deliberately
#: absent: it exists only in the 2026-07-28 modern protocol, which agent86's client cannot
#: negotiate (ClientSession.initialize() hardcodes LATEST_HANDSHAKE_VERSION).
_EXPECTED_IDS = (
    "CAP-TOOLS-LIST",
    "CAP-TOOLS-CALL",
    "CAP-TOOL-ANNOTATIONS",
    "CAP-STRUCTURED-OUTPUT",
    "CAP-CONTENT-BLOCKS",
    "CAP-RESOURCES",
    "CAP-RESOURCE-TEMPLATES",
    "CAP-RESOURCE-SUBSCRIBE",
    "CAP-PROMPTS",
    "CAP-COMPLETION",
    "CAP-SAMPLING",
    "CAP-ELICITATION",
    "CAP-ROOTS",
    "CAP-LOGGING",
    "CAP-PROGRESS",
    "CAP-CANCELLATION",
    "CAP-PAGINATION",
    "CAP-PING",
    "CAP-LIST-CHANGED",
    "CAP-META",
    "CAP-TRANSPORTS",
    "CAP-OAUTH",
)

_RATINGS = {"implemented", "partial", "absent"}
_RULINGS = {"in", "out"}
_COLUMNS = ("id", "capability", "rating", "corpus", "ruling", "reasoning")


def _matrix_rows() -> dict[str, dict[str, str]]:
    """Parse the matrix's capability table into {ID: {column: cell}}.

    A capability row is any markdown table row whose first cell starts with ``CAP-``.
    """
    rows: dict[str, dict[str, str]] = {}
    for line in _MATRIX.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or not cells[0].startswith("CAP-"):
            continue
        assert len(cells) == len(_COLUMNS), f"{cells[0]}: expected {len(_COLUMNS)} columns"
        rows[cells[0]] = dict(zip(_COLUMNS, cells, strict=True))
    return rows


def _section_15() -> str:
    text = _ARCH.read_text(encoding="utf-8")
    marker = "## 15."
    assert marker in text, "ARCHITECTURE.md lost its section 15 heading"
    return text[text.index(marker) :]


def test_matrix_pins_the_protocol_revision():
    assert "Protocol revision: 2025-11-25" in _MATRIX.read_text(encoding="utf-8")


def test_matrix_has_one_row_per_client_side_capability():
    assert set(_matrix_rows()) == set(_EXPECTED_IDS)


def test_every_row_rates_implementation():
    for cap_id, row in _matrix_rows().items():
        assert row["rating"].lower() in _RATINGS, f"{cap_id}: bad rating {row['rating']!r}"


def test_every_row_records_whether_a_corpus_server_exercises_it():
    for cap_id, row in _matrix_rows().items():
        assert row["corpus"], f"{cap_id}: empty corpus column"


def test_every_row_carries_a_ruling_with_written_reasoning():
    for cap_id, row in _matrix_rows().items():
        assert row["ruling"].lower() in _RULINGS, f"{cap_id}: bad ruling {row['ruling']!r}"
        assert len(row["reasoning"]) >= 20, f"{cap_id}: reasoning too thin"


def test_every_out_ruling_lands_in_architecture_section_15():
    section = _section_15()
    out = [c for c, r in _matrix_rows().items() if r["ruling"].lower() == "out"]
    missing = [c for c in out if c not in section]
    assert not missing, f"out-ruled but absent from ARCHITECTURE.md section 15: {missing}"


def test_four_adrs_exist_each_stating_a_decision():
    adrs = sorted(_ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md"))
    assert len(adrs) == 4, f"expected 4 numbered ADRs, found {[p.name for p in adrs]}"
    for path in adrs:
        body = path.read_text(encoding="utf-8")
        for heading in ("## Context", "## Decision", "## Consequences"):
            assert heading in body, f"{path.name} missing {heading}"
        assert "**Ruling:**" in body, f"{path.name} states no ruling"
