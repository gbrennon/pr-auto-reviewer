---
id: kotlin-scope-functions
language: kotlin
priority: 65
category: best-practices
---

# Kotlin Scope Functions Review

Review the following Kotlin code for proper scope function usage:

```kotlin
{{ code }}
```

## Checks

- Using `let` where `also` would be more appropriate (and vice versa)
- Nesting scope functions more than 2 levels deep (hurts readability)
- Using `run` on non-nullable receivers when `with` would be clearer
- `apply` used for side effects that don't configure the object
- Chaining `?.let { it.let { ... } }` — unnecessary nesting with `it`
- Shadowing outer `this` with inner scope function receivers
- Using scope functions to avoid naming intermediate values — make code harder to debug

## Good Example

```kotlin
fun buildUser(request: CreateUserRequest): User {
    return User(
        name = request.name.trim(),
        email = request.email.lowercase()
    ).also { user ->
        validateUser(user)
        auditLog.recordCreation(user)
    }
}

fun updateConfig(config: Config): Config = config.apply {
    lastModified = Clock.System.now()
    version += 1
}
```

## Bad Example

```kotlin
fun processRequest(request: Request?): Result {
    return request?.let { req ->
        req.body?.let { body ->
            body.params?.let { params ->
                params["id"]?.let { id ->
                    findUser(id)?.let { user ->
                        Result(user)
                    }
                }
            }
        }
    } ?: Result.Error("Invalid request")
    // Deeply nested let chain — hard to follow, hard to debug
}
```
