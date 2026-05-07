"""Tests for HashStore — mutable persisted-query hash registry."""

import json
from pathlib import Path

import pytest

from texas_grocery_mcp.clients.graphql import HashStore


def test_defaults_visible_via_dict_protocol():
    store = HashStore({"opA": "hashA", "opB": "hashB"})
    assert store["opA"] == "hashA"
    assert "opA" in store
    assert "opC" not in store
    assert store.get("opC") is None
    assert store.get("opC", "fallback") == "fallback"
    assert sorted(store.keys()) == ["opA", "opB"]
    assert dict(store.items()) == {"opA": "hashA", "opB": "hashB"}
    assert len(store) == 2


def test_overrides_loaded_from_cache_file_at_construction(tmp_path: Path):
    cache = tmp_path / "overrides.json"
    cache.write_text(json.dumps({"opA": "rotated"}))

    store = HashStore({"opA": "original", "opB": "original_b"}, cache_path=cache)

    assert store["opA"] == "rotated"
    assert store["opB"] == "original_b"


def test_malformed_cache_file_does_not_break_init(tmp_path: Path):
    cache = tmp_path / "overrides.json"
    cache.write_text("{not valid json")

    store = HashStore({"opA": "hashA"}, cache_path=cache)

    assert store["opA"] == "hashA"  # falls back to defaults


def test_non_dict_cache_file_is_ignored(tmp_path: Path):
    cache = tmp_path / "overrides.json"
    cache.write_text(json.dumps(["not", "a", "dict"]))

    store = HashStore({"opA": "hashA"}, cache_path=cache)

    assert store["opA"] == "hashA"


def test_cache_file_with_non_string_values_is_filtered(tmp_path: Path):
    cache = tmp_path / "overrides.json"
    cache.write_text(json.dumps({"opA": "valid", "opB": 123, "opC": None}))

    store = HashStore({"opA": "default_a"}, cache_path=cache)

    assert store["opA"] == "valid"
    assert store.get("opB") is None
    assert store.get("opC") is None


@pytest.mark.asyncio
async def test_rotate_returns_only_changed_entries(tmp_path: Path):
    store = HashStore({"opA": "old_a", "opB": "old_b"}, cache_path=tmp_path / "o.json")

    changed = await store.rotate({"opA": "new_a", "opB": "old_b", "opC": "new_c"})

    assert changed == {"opA": "new_a", "opC": "new_c"}
    assert store["opA"] == "new_a"
    assert store["opB"] == "old_b"
    assert store["opC"] == "new_c"


@pytest.mark.asyncio
async def test_rotate_persists_only_overrides_to_cache(tmp_path: Path):
    cache = tmp_path / "overrides.json"
    store = HashStore({"opA": "old_a", "opB": "old_b"}, cache_path=cache)

    await store.rotate({"opA": "new_a", "opB": "old_b"})

    persisted = json.loads(cache.read_text())
    # Only opA diverges from defaults; opB is unchanged so it shouldn't be written.
    assert persisted == {"opA": "new_a"}


@pytest.mark.asyncio
async def test_rotate_skips_empty_or_falsy_values(tmp_path: Path):
    store = HashStore({"opA": "old_a"}, cache_path=tmp_path / "o.json")

    changed = await store.rotate({"opA": "", "opB": None})  # type: ignore[dict-item]

    assert changed == {}
    assert store["opA"] == "old_a"


@pytest.mark.asyncio
async def test_rotate_no_persist_when_no_cache_path():
    store = HashStore({"opA": "old_a"}, cache_path=None)

    changed = await store.rotate({"opA": "new_a"})

    # In-memory rotation works even without a cache.
    assert changed == {"opA": "new_a"}
    assert store["opA"] == "new_a"


@pytest.mark.asyncio
async def test_rotate_creates_parent_directory(tmp_path: Path):
    cache = tmp_path / "nested" / "deep" / "overrides.json"
    store = HashStore({"opA": "old_a"}, cache_path=cache)

    await store.rotate({"opA": "new_a"})

    assert cache.exists()


@pytest.mark.asyncio
async def test_rotate_no_op_does_not_write_file(tmp_path: Path):
    cache = tmp_path / "overrides.json"
    store = HashStore({"opA": "hashA"}, cache_path=cache)

    await store.rotate({"opA": "hashA"})  # same value as default

    assert not cache.exists()


@pytest.mark.asyncio
async def test_rotate_subsequent_call_appends_overrides(tmp_path: Path):
    cache = tmp_path / "overrides.json"
    store = HashStore({"opA": "old_a", "opB": "old_b"}, cache_path=cache)

    await store.rotate({"opA": "new_a"})
    await store.rotate({"opB": "new_b"})

    persisted = json.loads(cache.read_text())
    assert persisted == {"opA": "new_a", "opB": "new_b"}


def test_overrides_property_returns_only_diverged_entries():
    store = HashStore({"opA": "x", "opB": "y"})
    # No cache, no rotations yet → no overrides
    assert store.overrides == {}
