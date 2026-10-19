from typing import Required, TypedDict


class ReviewScenarioInput(TypedDict, total=False):
    """Input scenario with only required parameters."""

    platform: Required[str]
    owner: Required[str]
    repo: Required[str]
    pr_id: Required[int]
    expected_items: int
    output_path: str
