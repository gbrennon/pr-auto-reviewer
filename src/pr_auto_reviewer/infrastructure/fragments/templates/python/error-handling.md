---
id: python-error-handling
language: python
priority: 80
category: error-handling
---

# Python Error Handling Best Practices

Review the following code for proper error handling:

```
{{ code }}
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
