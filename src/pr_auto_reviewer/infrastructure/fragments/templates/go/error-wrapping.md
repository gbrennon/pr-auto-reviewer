---
id: go-error-wrapping
language: go
priority: 80
category: best-practices
---

# Go Error Wrapping Review

Review the following Go code for proper error handling:

```go
{{ code }}
```

## Checks

- Plain `return err` without wrapping context
- Missing `fmt.Errorf("...: %w", err)` for sentinel error chains
- Using `errors.Is()` and `errors.As()` incorrectly
- Swallowing errors with `_ = doSomething()`
- Panicking when returning an error would suffice

## Good Example

```go
import (
	"errors"
	"fmt"
)

var ErrConfigNotFound = errors.New("config not found")

func loadConfig(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("loadConfig: reading %s: %w", path, err)
	}
	if len(data) == 0 {
		return nil, ErrConfigNotFound
	}
	return parseConfig(data)
}
```

## Bad Example

```go
func loadConfig(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err  // Context lost — which file failed?
	}
	return parseConfig(data)
}
```
