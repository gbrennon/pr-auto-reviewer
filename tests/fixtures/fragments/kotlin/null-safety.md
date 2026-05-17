---
id: kotlin-null-safety
language: kotlin
priority: 90
category: correctness
---

# Kotlin Null Safety Review

Review the following Kotlin code for null safety issues:

```kotlin
{{ code }}
```

## Checks

- Using `!!` (not-null assertion) which defeats the type system
- Platform types from Java interop used without null checks
- `lateinit var` without initialization guarantee
- Returning nullable types where a sealed class result type would be clearer
- `?.let {}` chains that could be simplified with early returns

## Good Example

```kotlin
class UserService(private val repository: UserRepository) {

    fun getProfile(userId: Long): UserProfile {
        val user = repository.findById(userId)
            ?: throw NotFoundException("User $userId not found")
        return buildProfile(user)
    }

    fun findByEmail(email: String): User? {
        if (email.isBlank()) return null
        return repository.findByEmail(email)
    }
}
```

## Bad Example

```kotlin
class UserService(private val repository: UserRepository) {

    fun getProfile(userId: Long): UserProfile {
        val user = repository.findById(userId)!!
        return buildProfile(user)
    }
}
```
