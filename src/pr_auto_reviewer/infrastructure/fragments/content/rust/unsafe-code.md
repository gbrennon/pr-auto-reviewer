---
id: rust-unsafe-code
language: rust
priority: 95
category: safety
---

# Rust Unsafe Code Review

Review the following Rust code for unsafe block safety:

```rust
{{ code }}
```

## Checks

- `unsafe` blocks without `// SAFETY:` comments explaining the invariants
- Raw pointer dereferencing without null or alignment checks
- FFI calls without proper error or null pointer handling
- `unsafe` code that could be rewritten using safe abstractions
- Unnecessary `unsafe` — transmute, unchecked indexing when safe alternatives exist
- Calling unsafe functions without verifying their documented preconditions
- Using `unsafe` in a public API without encapsulation

## Good Example

```rust
/// Returns a slice covering a sub-range of this slice.
///
/// # Safety
///
/// The caller must ensure that `start` and `end` are valid indices
/// within the underlying allocation and that the resulting reference
/// does not outlive the original data.
pub unsafe fn sub_slice(data: &[u8], start: usize, end: usize) -> &[u8] {
    // SAFETY: The caller guarantees that start..end is within bounds
    // and the returned reference lifetime is valid.
    unsafe { data.get_unchecked(start..end) }
}
```

## Bad Example

```rust
pub fn get_item(data: &[u8], index: usize) -> u8 {
    unsafe { *data.as_ptr().add(index) }  // No bounds check, no SAFETY comment
}
```
