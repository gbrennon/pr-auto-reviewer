---
id: documentation
language: null
priority: 40
category: quality
---

# Documentation Review

Review the changes for adequate documentation:

```
{{ code }}
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
