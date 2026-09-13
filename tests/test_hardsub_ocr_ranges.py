import pytest
from pydantic import ValidationError
from schemas.requests import HardsubExtractRequest
from engines.hardsub_ocr.ocr._runtime import _normalize_ranges


def test_normalize_ranges_merging():
    # Empty
    assert _normalize_ranges(None) == []
    assert _normalize_ranges([]) == []

    # Single range
    assert _normalize_ranges([[1.0, 5.0]]) == [(1.0, 5.0)]

    # Disjoint ranges
    ranges = [[1.0, 3.0], [5.0, 7.0]]
    assert _normalize_ranges(ranges, min_gap=0.5) == [(1.0, 3.0), (5.0, 7.0)]

    # Overlapping ranges
    ranges = [[1.0, 4.0], [3.5, 6.0]]
    assert _normalize_ranges(ranges, min_gap=0.5) == [(1.0, 6.0)]

    # Close ranges within min_gap
    ranges = [[1.0, 3.0], [3.2, 5.0]]
    assert _normalize_ranges(ranges, min_gap=0.5) == [(1.0, 5.0)]

    # Unsorted input
    ranges = [[10.0, 12.0], [1.0, 3.0], [2.5, 4.0]]
    assert _normalize_ranges(ranges, min_gap=0.5) == [(1.0, 4.0), (10.0, 12.0)]


def test_hardsub_extract_request_validation():
    # Valid
    req = HardsubExtractRequest(time_ranges=[[0.0, 2.5], [10.0, 15.0]])
    assert req.time_ranges == [[0.0, 2.5], [10.0, 15.0]]

    # Invalid range structure
    with pytest.raises(ValidationError):
        HardsubExtractRequest(time_ranges=[[1.0]])

    # Invalid range start < 0
    with pytest.raises(ValidationError):
        HardsubExtractRequest(time_ranges=[[-1.0, 5.0]])

    # Invalid range end < start
    with pytest.raises(ValidationError):
        HardsubExtractRequest(time_ranges=[[5.0, 2.0]])
