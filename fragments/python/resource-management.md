---
id: python-resource-management
language: python
priority: 75
category: security
---

# Python Resource Management Review

Review the following code for resource management issues:

```python
{{ code }}
```

## Checks

- Files opened without context managers (`with open(...)`)
- Database connections not closed in `finally` blocks
- Network sockets not properly shutdown
- Temporary files not cleaned up via `tempfile` or `try/finally`
- Locks/RLocks not released on exceptions
- Subprocess handles not waited on

## Good Example

```python
import sqlite3

def query_users(db_path: str) -> list[dict]:
    with sqlite3.connect(db_path) as conn:
        with conn:
            cursor = conn.execute("SELECT * FROM users")
            return [dict(row) for row in cursor.fetchall()]
```

## Bad Example

```python
def query_users(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT * FROM users")
    return cursor.fetchall()
    # Connection leaked!
```
