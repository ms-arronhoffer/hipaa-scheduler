"""Tests for interval subtraction in slot_generator.

_subtract is the core primitive of slot generation: it removes appointment
and time-off blocks from availability windows. It is pure and worth testing
directly with property-based invariants.
"""
from datetime import datetime, timedelta

from hypothesis import given, strategies as st

from app.services.slot_generator import _subtract


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 5, hour, minute)


class TestSubtract:
    def test_no_blocks_returns_base(self):
        base = [(_dt(9), _dt(17))]
        assert _subtract(base, []) == base

    def test_block_fully_contained_splits_window(self):
        result = _subtract([(_dt(9), _dt(17))], [(_dt(12), _dt(13))])
        assert result == [(_dt(9), _dt(12)), (_dt(13), _dt(17))]

    def test_block_at_start_trims_left(self):
        result = _subtract([(_dt(9), _dt(17))], [(_dt(9), _dt(10))])
        assert result == [(_dt(10), _dt(17))]

    def test_block_at_end_trims_right(self):
        result = _subtract([(_dt(9), _dt(17))], [(_dt(16), _dt(17))])
        assert result == [(_dt(9), _dt(16))]

    def test_block_covers_whole_window_removes_it(self):
        result = _subtract([(_dt(9), _dt(17))], [(_dt(8), _dt(18))])
        assert result == []

    def test_block_outside_window_no_op(self):
        base = [(_dt(9), _dt(17))]
        assert _subtract(base, [(_dt(18), _dt(19))]) == base
        assert _subtract(base, [(_dt(7), _dt(8))]) == base

    def test_multiple_blocks_applied_sequentially(self):
        result = _subtract(
            [(_dt(9), _dt(17))],
            [(_dt(10), _dt(11)), (_dt(14), _dt(15))],
        )
        assert result == [(_dt(9), _dt(10)), (_dt(11), _dt(14)), (_dt(15), _dt(17))]


# ---- property tests ----

_MINUTES = st.integers(min_value=0, max_value=1440)


def _to_dt(m: int) -> datetime:
    return datetime(2026, 1, 5) + timedelta(minutes=m)


@st.composite
def _interval(draw):
    a = draw(_MINUTES)
    b = draw(_MINUTES)
    lo, hi = min(a, b), max(a, b)
    if lo == hi:
        hi = lo + 1
    return (_to_dt(lo), _to_dt(hi))


class TestSubtractInvariants:
    @given(base=_interval(), blocks=st.lists(_interval(), max_size=5))
    def test_result_never_exceeds_base(self, base, blocks):
        result = _subtract([base], blocks)
        base_s, base_e = base
        for rs, re in result:
            assert base_s <= rs < re <= base_e

    @given(base=_interval(), blocks=st.lists(_interval(), max_size=5))
    def test_result_intervals_are_non_overlapping_and_sorted(self, base, blocks):
        result = _subtract([base], blocks)
        for i in range(len(result) - 1):
            assert result[i][1] <= result[i + 1][0]

    @given(base=_interval(), blocks=st.lists(_interval(), max_size=5))
    def test_no_point_in_result_lies_inside_any_block(self, base, blocks):
        result = _subtract([base], blocks)
        for rs, re in result:
            # Sample midpoint of each result interval; it must not fall in any block.
            mid = rs + (re - rs) / 2
            for bs, be in blocks:
                assert not (bs <= mid < be)
