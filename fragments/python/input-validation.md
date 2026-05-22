---
id: python-input-validation
language: python
priority: 90
category: security
---

# Python Input Validation & Security Review

Review the following code for security vulnerabilities:

```python
{{ code }}
```

## Checks

- User-provided input passed directly to SQL queries (SQL injection)
- Command injection via `os.system()`, `subprocess` with `shell=True`
- Deserialization of untrusted data (`pickle.loads()`, `marshal.loads()`)
- Path traversal via unsanitized user input in file operations
- Missing input validation on API endpoints
- Hardcoded secrets or API keys

## Good Example

```python
import re
from pathlib import Path

def read_user_file(user_input: str, base_dir: Path) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", user_input)
    target = (base_dir / sanitized).resolve()
    if not str(target).startswith(str(base_dir.resolve())):
        raise ValueError("Path traversal attempt detected")
    return target.read_text()
```

## Bad Example

```python
def read_user_file(filename: str) -> str:
    # UNSAFE: allows ../../etc/passwd
    return open(filename).read()
```
