---
id: test-coverage
language: null
priority: 70
category: quality
---

# Test Coverage Review

Review the changes for adequate testing:

```
{{ code }}
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
