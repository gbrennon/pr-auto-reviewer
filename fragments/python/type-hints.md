---
id: python-type-hints
language: python
priority: 70
category: best-practices
---

# Python Type Hints Review

Check the following code for proper type annotation usage:

```python
{{ code }}
```

## Checks

{% if 'def ' in code and ':' not in code.split('def ')[-1].split(')')[0] + ')' %}
⚠️ **Missing type hints** — function signatures should include parameter and return types
{% endif %}

- Missing parameter type annotations
- Missing return type annotation (`-> None` for void functions)
- Overly broad types (`Any` when a narrower type applies)
- Incorrect use of `Optional` vs `Union[None, T]`
- Missing `from __future__ import annotations` for forward references

## Good Example

```python
from __future__ import annotations
from typing import Optional

def find_user(user_id: int) -> Optional[dict[str, str]]:
    """Look up a user and return their details or None."""
    ...
```

## Bad Example

```python
def find_user(user_id):
    return db.query("SELECT * FROM users WHERE id = ?", user_id)
```
