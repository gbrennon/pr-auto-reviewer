---
id: go-context-usage
language: go
priority: 75
category: best-practices
---

# Go Context Usage Review

Review the following Go code for proper `context.Context` usage:

```go
{{ code }}
```

## Checks

- Creating `context.Background()` inside a function that could accept one
- Missing context cancellation propagation to child operations
- `context.TODO()` in production code
- Long-running operations without context deadline/timeout
- Storing context in struct fields (should be per-request)
- Forgetting to call `cancel()` from `context.WithCancel`

## Good Example

```go
func processWithTimeout(ctx context.Context, input string) (string, error) {
	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	resultCh := make(chan string, 1)
	errCh := make(chan error, 1)

	go func() {
		result, err := expensiveOperation(ctx, input)
		if err != nil {
			errCh <- err
			return
		}
		resultCh <- result
	}()

	select {
	case result := <-resultCh:
		return result, nil
	case err := <-errCh:
		return "", err
	case <-ctx.Done():
		return "", ctx.Err()
	}
}
```

## Bad Example

```go
func process(input string) (string, error) {
	ctx := context.Background()  // No deadline, not passed to children
	go expensiveOperation(ctx, input)  // Fire and forget, context not used
	return "done", nil
}
```
