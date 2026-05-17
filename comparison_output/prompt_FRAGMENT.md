# SOLID Principles Review

Check for violations of SOLID principles:

```
+    if not username or not password:
+        raise ValueError("Username and password required")
-        user = db.query("SELECT * FROM users WHERE name = '" + username + "'")
+        user = db.query(
+            "SELECT * FROM users WHERE name = ?",
+            [username]
+        )
```

## Single Responsibility Principle
- Each class/module should have one reason to change
- Look for "god classes" with multiple unrelated responsibilities

## Open/Closed Principle
- Open for extension, closed for modification
- Avoid long if/switch chains for type checking

## Liskov Substitution Principle
- Subtypes must be substitutable for base types
- Check for method signature violations in overrides

## Interface Segregation Principle
- Clients shouldn't depend on interfaces they don't use
- Look for fat interfaces

## Dependency Inversion Principle
- Depend on abstractions, not concretions
- Check for `new ConcreteClass()` instantiations

---

# Python Input Validation & Security Review

Review the following code for security vulnerabilities:

```python
+    if not username or not password:
+        raise ValueError("Username and password required")
-        user = db.query("SELECT * FROM users WHERE name = '" + username + "'")
+        user = db.query(
+            "SELECT * FROM users WHERE name = ?",
+            [username]
+        )
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

---

# Python Error Handling Best Practices

Review the following code for proper error handling:

```
+    if not username or not password:
+        raise ValueError("Username and password required")
-        user = db.query("SELECT * FROM users WHERE name = '" + username + "'")
+        user = db.query(
+            "SELECT * FROM users WHERE name = ?",
+            [username]
+        )
```

## Checks

- Bare `except:` clauses (should specify exception types)
- Missing exception context (`raise` without `from`)
- Resource leaks (files/connections not in `with` statements)
- Swallowed exceptions (empty except blocks)

## Good Example

```python
try:
    with open(file_path) as f:
        data = json.load(f)
except FileNotFoundError as e:
    raise ConfigError(f"Config not found: {file_path}") from e
except json.JSONDecodeError as e:
    raise ConfigError(f"Invalid JSON in {file_path}") from e
```

## Bad Example

```python
try:
    f = open(file_path)
    data = json.load(f)
except:
    pass
```

---

# Python Resource Management Review

Review the following code for resource management issues:

```python
+    if not username or not password:
+        raise ValueError("Username and password required")
-        user = db.query("SELECT * FROM users WHERE name = '" + username + "'")
+        user = db.query(
+            "SELECT * FROM users WHERE name = ?",
+            [username]
+        )
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

---

# Python Type Hints Review

Check the following code for proper type annotation usage:

```python
+    if not username or not password:
+        raise ValueError("Username and password required")
-        user = db.query("SELECT * FROM users WHERE name = '" + username + "'")
+        user = db.query(
+            "SELECT * FROM users WHERE name = ?",
+            [username]
+        )
```

## Checks


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

---

# Test Coverage Review

Review the changes for adequate testing:

```
+    if not username or not password:
+        raise ValueError("Username and password required")
-        user = db.query("SELECT * FROM users WHERE name = '" + username + "'")
+        user = db.query(
+            "SELECT * FROM users WHERE name = ?",
+            [username]
+        )
```

## Checks

- New functionality without corresponding tests
- Modified logic that invalidates existing test assumptions
- Edge cases not covered (empty inputs, null values, boundary conditions)
- Error paths without test coverage
- Test files modified without adding or updating assertions
- Overly broad `except:` blocks in tests (hides failures)

## Good Practice

```
# Every function has a corresponding test
def test_divide_by_zero_raises():
    with pytest.raises(ZeroDivisionError):
        calculator.divide(10, 0)

def test_empty_list_returns_zero():
    assert sum_positive([]) == 0
```

## Bad Practice

```
# New feature without tests
def calculate_discount(price, user_type):
    if user_type == "premium":
        return price * 0.8
    return price
# Where is the test for premium users? For non-premium?
```

---

# Python Async/Await Review

Review the following code for proper async/await usage:

```python
+    if not username or not password:
+        raise ValueError("Username and password required")
-        user = db.query("SELECT * FROM users WHERE name = '" + username + "'")
+        user = db.query(
+            "SELECT * FROM users WHERE name = ?",
+            [username]
+        )
```

## Checks

- `asyncio.run()` called inside an already-running event loop
- Blocking I/O calls (`open()`, `requests.get()`) inside async functions
- Missing `await` on coroutine calls (coroutine was never awaited)
- Fire-and-forget tasks without error handling (`task = asyncio.create_task(...)`)
- Mixing `asyncio` with `concurrent.futures` without `run_in_executor()`

## Good Example

```python
import asyncio
import aiohttp

async def fetch_url(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

## Bad Example

```python
async def bad_fetch(url: str) -> dict:
    import requests
    # Blocking call inside async function!
    return requests.get(url).json()
```

---

# Naming Conventions Review

Review the code for proper naming conventions:

```
+    if not username or not password:
+        raise ValueError("Username and password required")
-        user = db.query("SELECT * FROM users WHERE name = '" + username + "'")
+        user = db.query(
+            "SELECT * FROM users WHERE name = ?",
+            [username]
+        )
```

## Checks

- Single-letter variable names (except `i`, `j` for loop indexes)
- Abbreviations that obscure meaning (`fn`, `proc`, `mgr`)
- Inconsistent casing (mixing camelCase and snake_case)
- Boolean variables without `is_` / `has_` / `should_` prefix
- Constants not in UPPER_SNAKE_CASE
- Generic names (`data`, `info`, `result`, `temp`) — prefer descriptive names
- File/folder names following project conventions

## Good Practice

```
# Descriptive, searchable names
user_email_address = "user@example.com"
is_authenticated = True
MAX_RETRY_COUNT = 3

def calculate_total_price(items: list[Item]) -> Decimal:
    ...
```

## Bad Practice

```
# Hard to understand, impossible to search
d = "user@example.com"
f = True
m = 3

def calc(itms):
    ...
```

---

# Documentation Review

Review the changes for adequate documentation:

```
+    if not username or not password:
+        raise ValueError("Username and password required")
-        user = db.query("SELECT * FROM users WHERE name = '" + username + "'")
+        user = db.query(
+            "SELECT * FROM users WHERE name = ?",
+            [username]
+        )
```

## Checks

- New public functions/classes missing docstrings
- Docstrings that only repeat the function name
- Missing parameter and return value documentation
- Inline comments that explain "what" instead of "why"
- Outdated comments that no longer match the code
- Missing README / module docstring for new packages
- Magic numbers without explanatory comments

## Good Example

```python
def retry_operation(
    func: Callable[[], T],
    max_attempts: int = 3,
    backoff: float = 2.0,
) -> T:
    """Retry a callable with exponential backoff.

    Args:
        func: The callable to execute. Must be idempotent.
        max_attempts: Maximum number of retries before giving up.
        backoff: Multiplier for exponential delay between attempts.

    Returns:
        The return value of *func* on success.

    Raises:
        MaxRetriesExceededError: If all attempts fail.
    """
```

## Bad Example

```python
# Do the thing
def do(x):
    # Loop
    for i in range(3):
        try:
            return x()  # Call it
        except:
            pass  # Ignore errors
    raise Exception("Failed")
```