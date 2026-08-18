"""ReasonFactory — builds an expressive reason string from review items."""

from pr_auto_reviewer.domain.entities.review_item import ReviewItem


class ReasonFactory:
    """Builds an expressive reason string from a list of review items."""

    def make(self, items: list[ReviewItem]) -> str:
        """Group items by severity and category into a human-readable sentence.

        Returns ``"No issues found."`` when the item list is empty.
        """
        if not items:
            return "No issues found."

        severity_groups: dict[str, list[ReviewItem]] = {
            "critical": [],
            "major": [],
            "minor": [],
            "info": [],
        }
        for item in items:
            severity_groups[str(item.severity)].append(item)

        severity_strings: list[str] = []
        for severity in ("critical", "major", "minor", "info"):
            group = severity_groups[severity]
            if not group:
                continue
            count = len(group)
            category_counts: dict[str, int] = {}
            for item in group:
                cat = str(item.category)
                category_counts[cat] = category_counts.get(cat, 0) + 1
            sorted_cats = sorted(category_counts.items(), key=lambda kv: kv[0])
            cat_detail = ", ".join(
                f"{cnt} {cat}" for cat, cnt in sorted_cats
            )
            severity_strings.append(f"{count} {severity} ({cat_detail})")

        if len(severity_strings) == 1:
            return f"Found {severity_strings[0]}."
        elif len(severity_strings) == 2:
            return f"Found {severity_strings[0]} and {severity_strings[1]}."
        *init, last = severity_strings
        return f"Found {', '.join(init)}, and {last}."
