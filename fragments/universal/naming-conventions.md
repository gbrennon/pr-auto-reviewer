---
id: naming-conventions
language: null
priority: 50
category: style
---

# Naming Conventions Review

Review the code for proper naming conventions:

```
{{ code }}
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
