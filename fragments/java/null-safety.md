---
id: java-null-safety
language: java
priority: 80
category: correctness
---

# Java Null Safety Review

Review the following Java code for null safety issues:

```java
{{ code }}
```

## Checks

- Returning `null` from methods that could return `Optional<T>` instead
- Dereferencing method results without null checks
- `Optional.get()` called without `isPresent()` check
- Using `Optional` as fields or parameters (Java best practice: only for return types)
- Passing `null` as arguments where `@NonNull` is expected
- `Optional.of()` with potentially null value (use `ofNullable()`)
- Chained calls without null guards on intermediate results

## Good Example

```java
public class UserService {
    private final UserRepository repository;

    public Optional<User> findByEmail(String email) {
        if (email == null || email.isBlank()) {
            return Optional.empty();
        }
        return repository.findByEmail(email);
    }

    public UserProfile getProfile(long userId) {
        return findById(userId)
            .map(this::buildProfile)
            .orElseThrow(() -> new NotFoundException("User " + userId));
    }
}
```

## Bad Example

```java
public class UserService {
    public User findByEmail(String email) {
        return repository.findByEmail(email);  // Returns null — caller doesn't know
    }

    public String getDisplayName(long userId) {
        User user = findById(userId);
        return user.getName().toUpperCase();  // NPE if user is null
    }
}
```
