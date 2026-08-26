from ._shared import *


class RetryPromptBuilder:
    def build_correction_prompt(self, original_prompt: str, failures: list[str]) -> str:
        header = (
            "Your previous response did not follow the required review schema. "
        )
        missing = "; ".join(failures)
        instruction = f"Fix these issues: {missing}."
        return (
            f"{header}{instruction}\n\n"
            "Return JSON with the exact fields requested. Each issue must have: "
            "file, description (a text string, not an object), severity, category, "
            "current_code (exact code from the diff), suggested_fix.\n\n"
            f"--- Original request ---\n{original_prompt}"
        )

    def diagnose_failures(self, review: CodeReview) -> list[str]:
        failures: list[str] = []
        for i, item in enumerate(review.items):
            if not item.description:
                failures.append(f"item {i} is missing 'description'")
            if not item.current_code:
                failures.append(f"item {i} is missing 'current_code'")
            if not item.suggested_fix:
                failures.append(f"item {i} is missing 'suggested_fix'")
            if not item.file_path:
                failures.append(f"item {i} is missing 'file'")
        return failures

