from __future__ import annotations

import pytest

from uspto_client import PATENT_NUMBER_SEARCH, AssignmentCenterClient

PATENT_NUMBER = "11111279"
REEL_NUMBER = 46387
FRAME_NUMBER = 180


@pytest.mark.live
def test_live_assignment_center_search_and_reel_frame_lookup() -> None:
    with AssignmentCenterClient() as client:
        search = client.search_patents(
            PATENT_NUMBER,
            search_by=PATENT_NUMBER_SEARCH,
        )
        details = client.get_reel_frame(REEL_NUMBER, FRAME_NUMBER)

    assert search.total_rows == 1
    assert search.results[0].properties[0].patent_number == PATENT_NUMBER
    assert details.total_rows == 1
    assert details.results[0].assignment_records[0].reel_number == REEL_NUMBER
