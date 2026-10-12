from pr_auto_reviewer.domain import ReviewItemLifecycle, ReviewItemStatus


class TestReviewItemLifecycleTransitions:
    def test_audit_keeps_open_item_open_without_proof(self) -> None:
        lifecycle = ReviewItemLifecycle.first_appearance("item-1", "sha-1")
        open_lifecycle = lifecycle.audit("sha-2", proof=False)

        audited = open_lifecycle.audit("sha-3", proof=False, explanation="Still open")

        assert audited.status is ReviewItemStatus.OPEN
        assert audited.transitions[-1].from_status is ReviewItemStatus.OPEN
        assert audited.transitions[-1].to_status is ReviewItemStatus.OPEN

    def test_dismiss_open_lifecycle_records_terminal_transition(self) -> None:
        lifecycle = ReviewItemLifecycle.first_appearance("item-1", "sha-1")
        open_lifecycle = lifecycle.audit("sha-2", proof=False)

        dismissed = open_lifecycle.dismiss("sha-3", explanation="Not actionable")

        assert dismissed.status is ReviewItemStatus.DISMISSED
        assert dismissed.transitions[-1].from_status is ReviewItemStatus.OPEN
        assert dismissed.transitions[-1].to_status is ReviewItemStatus.DISMISSED
