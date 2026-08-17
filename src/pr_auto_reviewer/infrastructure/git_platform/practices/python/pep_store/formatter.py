from __future__ import annotations

from .types import PepEntry


class PepFormatter:
    def format(self, peps: list[PepEntry], python_version: str) -> str:
        lines: list[str] = [
            f"## Relevant Python PEPs (targeting Python {python_version}+)\n"
        ]
        for pep in peps:
            pep_num = pep.get("number", "?")
            title = pep.get("title", "Untitled")
            pep_type = pep.get("type", "")
            status = pep.get("status", "")
            url = pep.get("url", "")
            lines.append(
                f"- **PEP {pep_num}** ({pep_type}/{status}): "
                f"[{title}]({url})"
            )
        return "\n".join(lines)
