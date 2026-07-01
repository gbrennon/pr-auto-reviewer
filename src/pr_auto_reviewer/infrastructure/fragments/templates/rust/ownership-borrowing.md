---
id: rust-ownership-borrowing
language: rust
priority: 90
category: correctness
---

# Rust Ownership & Borrowing Review

Review the following Rust code for ownership and borrowing issues:

```rust
{{ code }}
```

## Checks

- Unnecessary `.clone()` calls — prefer borrowing or passing references
- Cloning `String` when `&str` would suffice
- Holding a `MutexGuard` across an `.await` point (not `Send`)
- Storing references in structs without proper lifetime annotations
- Using `Rc<RefCell<T>>` in single-threaded code where a simple `&mut T` would work
- Missing `&mut self` when the method modifies internal state
- Collecting into an owned `Vec` when an iterator would avoid allocation
- Boxing large values unnecessarily with `Box::new()`

## Good Example

```rust
pub struct UserService {
    repository: Box<dyn UserRepository>,
}

impl UserService {
    pub fn find_by_email(&self, email: &str) -> Option<&User> {
        self.repository.find(|u| u.email == email)
    }

    pub fn validate_names(users: &[User]) -> Vec<&str> {
        users.iter()
            .filter(|u| !u.name.is_empty())
            .map(|u| u.name.as_str())
            .collect()
    }
}
```

## Bad Example

```rust
pub struct UserService {
    repository: Box<dyn UserRepository>,
}

impl UserService {
    pub fn find_by_email(&self, email: String) -> Option<User> {
        self.repository.find(|u| u.email == email).cloned()
        // email parameter cloned unnecessarily (accept &str)
        // returned User cloned instead of returning a reference
    }
}
```
