---
id: rust-error-handling
language: rust
priority: 85
category: error-handling
---

# Rust Error Handling Review

Review the following Rust code for proper error handling:

```rust
{{ code }}
```

## Checks

- Using `unwrap()` or `expect()` in library code (should propagate errors with `?`)
- Silent error swallowing with `if let Err(_) = ...` or `let _ = ...`
- Using `String` as error type instead of proper `Error` trait implementation
- Missing context with `.context("...")?` from `anyhow` or `.map_err()` for meaningful errors
- Panicking instead of returning `Result` in fallible functions
- Converting errors with `?` without preserving the original error chain

## Good Example

```rust
use thiserror::Error;

#[derive(Error, Debug)]
pub enum ConfigError {
    #[error("failed to read config at {path}: {source}")]
    ReadError { path: String, source: std::io::Error },
    #[error("invalid config format")]
    ParseError(#[from] serde_json::Error),
}

pub fn load_config(path: &str) -> Result<Config, ConfigError> {
    let data = std::fs::read_to_string(path).map_err(|e| ConfigError::ReadError {
        path: path.to_string(),
        source: e,
    })?;
    let config: Config = serde_json::from_str(&data)?;
    Ok(config)
}
```

## Bad Example

```rust
pub fn load_config(path: &str) -> Result<Config, String> {
    let data = std::fs::read_to_string(path).unwrap();
    let config: Config = match serde_json::from_str(&data) {
        Ok(c) => c,
        Err(_) => return Err("parse error".to_string()),
    };
    Ok(config)
}
```
