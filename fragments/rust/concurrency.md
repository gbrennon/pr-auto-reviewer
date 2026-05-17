---
id: rust-concurrency
language: rust
priority: 80
category: concurrency
---

# Rust Concurrency Review

Review the following Rust code for concurrency issues:

```rust
{{ code }}
```

## Checks

- Holding a `std::sync::MutexGuard` across `.await` points in async code
- Using `std::sync::Mutex` in async contexts (use `tokio::sync::Mutex` instead)
- Blocking synchronous I/O or long computations inside `async fn`
- Shared mutable state without proper synchronisation (`Mutex`, `RwLock`, or `Atomic*`)
- Deadlock potential — acquiring multiple locks in inconsistent order
- Channel operations with mismatched sender/receiver lifetimes
- `Send` + `Sync` trait violations when crossing thread boundaries
- Spawning blocking tasks without `tokio::task::spawn_blocking`

## Good Example

```rust
use std::sync::Arc;
use tokio::sync::Mutex;

pub struct Cache {
    data: Arc<Mutex<HashMap<String, String>>>,
}

impl Cache {
    pub async fn get(&self, key: &str) -> Option<String> {
        let guard = self.data.lock().await;
        guard.get(key).cloned()
        // Guard dropped here — safe to hold across await if needed
    }

    pub async fn insert(&self, key: String, value: String) {
        self.data.lock().await.insert(key, value);
    }
}
```

## Bad Example

```rust
use std::sync::Mutex;  // std Mutex in async context

pub async fn update(cache: &Mutex<HashMap<String, String>>, key: &str) {
    let guard = cache.lock().unwrap();  // Blocks the async runtime thread!
    tokio::time::sleep(Duration::from_secs(1)).await;
    // Guard still held across .await — potential deadlock
    println!("{:?}", guard.get(key));
}
```
