---
id: go-concurrency
language: go
priority: 85
category: concurrency
---

# Go Concurrency Patterns

Review goroutines and channel usage:

```
{{ code }}
```

## Checks

- Goroutines that might leak (no way to stop them)
- Unbuffered channels that might deadlock
- Missing `context.Context` for cancellation
- Race conditions on shared state

## Good Example

```go
func worker(ctx context.Context, jobs <-chan int) {
    for {
        select {
        case job := <-jobs:
            process(job)
        case <-ctx.Done():
            return
        }
    }
}
```
