"""Tests for the deterministic ID generator (investorlens.ids)."""

from __future__ import annotations

import pytest

from investorlens.ids import canonicalize, content_hash, make_id


class TestCanonicalize:
    def test_dict_key_order_doesnt_matter(self) -> None:
        a = canonicalize({"a": 1, "b": 2})
        b = canonicalize({"b": 2, "a": 1})
        assert a == b

    def test_none_values_are_dropped(self) -> None:
        # Important: two records that differ only in "missing" vs "null" should hash identically.
        a = canonicalize({"isin": "INE002A01018", "nse_symbol": None})
        b = canonicalize({"isin": "INE002A01018"})
        assert a == b

    def test_float_noise_absorbed(self) -> None:
        # 0.1 + 0.2 != 0.3 in float arithmetic; both should canonicalize to the same hash.
        a = canonicalize({"x": 0.1 + 0.2})
        b = canonicalize({"x": 0.3})
        assert a == b

    def test_strings_are_utf8_safe(self) -> None:
        # CJK / accented chars should not raise.
        s = canonicalize({"name": " Reliance Industries Ltd — रिलायंस "})
        assert isinstance(s, str)


class TestContentHash:
    def test_stable_length(self) -> None:
        h = content_hash({"a": 1})
        assert len(h) == 12
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_input_same_hash(self) -> None:
        a = content_hash({"isin": "INE002A01018"})
        b = content_hash({"isin": "INE002A01018"})
        assert a == b

    def test_different_input_different_hash(self) -> None:
        a = content_hash({"isin": "INE002A01018"})
        b = content_hash({"isin": "INE002A01019"})
        assert a != b


class TestMakeId:
    def test_company_id_format(self) -> None:
        cid = make_id("co", {"isin": "INE002A01018"})
        assert cid.startswith("co_")
        assert len(cid) == 3 + 12  # "co_" + 12 hex chars

    def test_id_deterministic(self) -> None:
        # Same input must produce the same ID across runs (idempotency).
        a = make_id("co", {"isin": "INE002A01018"})
        b = make_id("co", {"isin": "INE002A01018"})
        assert a == b

    def test_unknown_prefix_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown entity prefix"):
            make_id("xx", {"a": 1})

    def test_string_content_uses_string_directly(self) -> None:
        # When content is a string, the hash is over that string directly.
        a = make_id("co", "INE002A01018")
        b = make_id("co", "INE002A01018")
        assert a == b
        assert a != make_id("co", "INE002A01019")
