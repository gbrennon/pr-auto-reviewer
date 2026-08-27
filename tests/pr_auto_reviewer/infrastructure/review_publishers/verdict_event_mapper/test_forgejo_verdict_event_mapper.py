from ._helpers import *


class TestForgejoVerdictEventMapper:
    """Behaviour of ForgejoVerdictEventMapper.map(verdict) -> str."""

    def test_map_approve_verdict_is_approved(self) -> None:
        mapper = ForgejoVerdictEventMapper()
        assert mapper.map(ReviewVerdict.APPROVED) == "APPROVED"

    def test_map_changes_requested_is_request_changes(self) -> None:
        mapper = ForgejoVerdictEventMapper()
        assert mapper.map(ReviewVerdict.CHANGES_REQUESTED) == "REQUEST_CHANGES"

    def test_map_commented_is_comment(self) -> None:
        mapper = ForgejoVerdictEventMapper()
        assert mapper.map(ReviewVerdict.COMMENTED) == "COMMENT"

    def test_map_unknown_verdict_falls_back_to_comment(self) -> None:
        mapper = ForgejoVerdictEventMapper()
        assert mapper.map(cast(ReviewVerdict, "UNKNOWN")) == "COMMENT"
