from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict

# ruleid: python-code-review-no-commented-verdict
commented_review = CodeReview(
    verdict=ReviewVerdict.COMMENTED,
    reason="reason",
    summary="summary",
    model_used="model",
)

# ruleid: python-code-review-no-hardcoded-approved-verdict
approved_review = CodeReview(
    verdict=ReviewVerdict.APPROVED,
    reason="reason",
    summary="summary",
    model_used="model",
)

computed_verdict = ReviewVerdict.CHANGES_REQUESTED
valid_review = CodeReview(
    verdict=computed_verdict,
    reason="reason",
    summary="summary",
    model_used="model",
)
