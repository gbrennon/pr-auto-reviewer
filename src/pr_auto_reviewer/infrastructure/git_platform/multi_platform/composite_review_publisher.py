from pr_auto_reviewer.application.ports.outbound.review_publisher_port import (
    ReviewPublisherPort,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.git_platform.multi_platform._parse_platform_prefix import (
    split_repository_prefix,
)


class CompositeReviewPublisher(ReviewPublisherPort):
    def __init__(self, publishers: dict[str, ReviewPublisherPort]) -> None:
        self._publishers = publishers

    def publish(self, pr_id: PullRequestId, review: CodeReview, diff: PullRequestDiff | None = None) -> None:
        platform, repo_name = split_repository_prefix(pr_id.repository)
        publisher = self._publishers.get(platform)
        if not publisher:
            raise ValueError(f"No publisher for platform {platform} in {pr_id}")
        clean_id = PullRequestId(repository=repo_name, number=pr_id.number)
        publisher.publish(clean_id, review, diff)
