"""Tests for atomic, idempotent JSON I/O (investorlens.io)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from investorlens.io import read_json, read_jsonl, upsert_records, write_json, write_jsonl


@pytest.fixture
def tmp_jsonl(tmp_path: Path) -> Path:
    return tmp_path / "data.jsonl"


@pytest.fixture
def tmp_json(tmp_path: Path) -> Path:
    return tmp_path / "single.json"


class TestWriteJson:
    def test_atomic_write(self, tmp_json: Path) -> None:
        write_json(tmp_json, {"a": 1, "b": [1, 2, 3]})
        assert tmp_json.exists()
        assert read_json(tmp_json) == {"a": 1, "b": [1, 2, 3]}

    def test_canonical_output_sorted_keys(self, tmp_json: Path) -> None:
        write_json(tmp_json, {"b": 2, "a": 1, "c": 3})
        content = tmp_json.read_text(encoding="utf-8")
        # Keys must be sorted in the output.
        assert content.index('"a"') < content.index('"b"') < content.index('"c"')

    def test_rewrite_same_data_is_byte_identical(self, tmp_json: Path) -> None:
        data = {"a": 1, "b": [1, 2, 3]}
        write_json(tmp_json, data)
        first = tmp_json.read_bytes()
        # Reorder the dict — output must still be byte-identical (canonical).
        write_json(tmp_json, {"b": [1, 2, 3], "a": 1})
        second = tmp_json.read_bytes()
        assert first == second

    def test_no_partial_file_on_error(self, tmp_json: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """If serialization fails, the target file must not exist (or remain unchanged)."""
        # Pre-create the target with known content.
        write_json(tmp_json, {"existing": True})

        class NotSerializable:
            pass

        # Patch json.dumps to raise on our sentinel value.
        original_dumps = json.dumps

        def patched_dumps(*args, **kwargs):
            for arg in args:
                if isinstance(arg, NotSerializable):
                    raise TypeError("boom")
            return original_dumps(*args, **kwargs)

        monkeypatch.setattr("investorlens.io.json.dumps", patched_dumps)

        with pytest.raises(TypeError):
            write_json(tmp_json, {"bad": NotSerializable()})

        # The original file must be untouched.
        assert read_json(tmp_json) == {"existing": True}
        # No .tmp files left behind.
        leftover = list(tmp_json.parent.glob("*.tmp"))
        assert leftover == []


class TestWriteJsonl:
    def test_sorted_by_id(self, tmp_jsonl: Path) -> None:
        records = [
            {"id": "obs_zzz", "v": 3},
            {"id": "obs_aaa", "v": 1},
            {"id": "obs_mmm", "v": 2},
        ]
        write_jsonl(tmp_jsonl, records)
        lines = tmp_jsonl.read_text(encoding="utf-8").strip().split("\n")
        ids = [json.loads(line)["id"] for line in lines]
        assert ids == ["obs_aaa", "obs_mmm", "obs_zzz"]

    def test_empty_input(self, tmp_jsonl: Path) -> None:
        write_jsonl(tmp_jsonl, [])
        assert tmp_jsonl.exists()
        assert tmp_jsonl.read_text(encoding="utf-8") == ""


class TestUpsertRecords:
    def test_first_write_inserts_all(self, tmp_jsonl: Path) -> None:
        records = [
            {"id": "a", "v": 1},
            {"id": "b", "v": 2},
        ]
        stats = upsert_records(tmp_jsonl, records)
        assert stats == {"inserted": 2, "updated": 0, "total": 2}
        on_disk = read_jsonl(tmp_jsonl)
        assert {r["id"] for r in on_disk} == {"a", "b"}

    def test_second_write_idempotent_when_unchanged(self, tmp_jsonl: Path) -> None:
        records = [{"id": "a", "v": 1}]
        upsert_records(tmp_jsonl, records)
        # Re-upsert the same records — should report 0 inserts / 0 updates.
        stats = upsert_records(tmp_jsonl, records)
        assert stats == {"inserted": 0, "updated": 0, "total": 1}

    def test_update_existing(self, tmp_jsonl: Path) -> None:
        upsert_records(tmp_jsonl, [{"id": "a", "v": 1}])
        stats = upsert_records(tmp_jsonl, [{"id": "a", "v": 2}])
        assert stats == {"inserted": 0, "updated": 1, "total": 1}
        on_disk = read_jsonl(tmp_jsonl)
        assert on_disk[0]["v"] == 2

    def test_missing_key_raises(self, tmp_jsonl: Path) -> None:
        with pytest.raises(ValueError, match="missing required key"):
            upsert_records(tmp_jsonl, [{"v": 1}])  # no "id"

    def test_mixed_insert_and_update(self, tmp_jsonl: Path) -> None:
        upsert_records(tmp_jsonl, [{"id": "a", "v": 1}, {"id": "b", "v": 2}])
        stats = upsert_records(
            tmp_jsonl,
            [
                {"id": "a", "v": 99},  # update
                {"id": "c", "v": 3},   # insert
            ],
        )
        assert stats == {"inserted": 1, "updated": 1, "total": 3}
