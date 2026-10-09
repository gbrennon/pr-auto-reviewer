import json

from pr_auto_reviewer.domain import (
    CodeReview,
    CommitSha,
    ItemSeverity,
    PullRequest,
    PullRequestId,
    ReviewItem,
    ReviewItemLifecycle,
    ReviewItemStatus,
    ReviewItemTransition,
    ReviewVerdict,
)
from pr_auto_reviewer.infrastructure.persistence.json_file_pr_repository import (
    JsonFilePullRequestRepository,
)


def _item() -> ReviewItem:
    return ReviewItem(
        id="item-1",
        severity=ItemSeverity.MAJOR,
        category="bug",
        file_path="src/a.py",
        description="finding",
        current_code="before",
        suggested_fix="after",
        status=ReviewItemStatus.OPEN,
        status_explanation="Still present",
    )


def _review(item: ReviewItem) -> CodeReview:
    return CodeReview(
        verdict=ReviewVerdict.CHANGES_REQUESTED,
        reason="reason preserved",
        summary="summary",
        model_used="model",
        items=[item],
    )


def test_lifecycle_evidence_and_transition_round_trip(tmp_path) -> None:
    item = _item()
    lifecycle = ReviewItemLifecycle(
        item_id="item-1",
        status=ReviewItemStatus.OPEN,
        first_seen_sha="sha-1",
        last_audited_sha="sha-2",
        status_explanation="Still present",
        transitions=(
            ReviewItemTransition(
                from_status=None,
                to_status=ReviewItemStatus.CREATED,
                commit_sha="sha-1",
                explanation="First seen",
            ),
            ReviewItemTransition(
                from_status=ReviewItemStatus.CREATED,
                to_status=ReviewItemStatus.OPEN,
                commit_sha="sha-2",
                explanation="Still present",
            ),
        ),
    )
    pr = PullRequest(
        id=PullRequestId("owner/repo", 1),
        title="Test",
        head_sha=CommitSha("sha-2"),
        reviews=(_review(item),),
        lifecycles=(lifecycle,),
    )
    repository = JsonFilePullRequestRepository(tmp_path / "state.json")

    repository.save(pr)
    loaded = repository.find(pr.id)

    assert loaded is not None
    assert loaded.reviews[0].reason == "reason preserved"
    assert loaded.historical_items()[0].current_code == "before"
    assert loaded.historical_items()[0].suggested_fix == "after"
    assert loaded.historical_items()[0].status is ReviewItemStatus.OPEN
    assert loaded.historical_items()[0].status_explanation == "Still present"
    assert loaded.lifecycles[0].transitions == lifecycle.transitions


def test_old_snapshot_without_lifecycles_derives_projection(tmp_path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "reviewed": {
                    "owner/repo/1": {
                        "title": "Legacy",
                        "head_sha": "sha-1",
                        "reviews": [
                            {
                                "verdict": "approved",
                                "reason": "legacy reason",
                                "summary": "legacy summary",
                                "model_used": "legacy model",
                                "items": [
                                    {
                                        "id": "item-1",
                                        "severity": "minor",
                                        "category": "bug",
                                        "file_path": "src/a.py",
                                        "description": "legacy finding",
                                        "status": "open",
                                    }
                                ],
                            }
                        ],
                    }
                }
            }
        )
    )
    repository = JsonFilePullRequestRepository(state_path)

    loaded = repository.find(PullRequestId("owner/repo", 1))

    assert loaded is not None
    assert loaded.lifecycles[0].item_id == "item-1"
    assert loaded.lifecycles[0].status is ReviewItemStatus.OPEN
    assert loaded.historical_items()[0].description == "legacy finding"
