---
id: kotlin-data-classes
language: kotlin
priority: 75
category: best-practices
---

# Kotlin Data Classes Review

Review the following Kotlin code for proper data class usage:

```kotlin
{{ code }}
```

## Checks

- Data classes with `var` properties (should prefer `val` for immutability)
- Data classes containing mutable collections without defensive copies
- Using regular classes where `data class` would provide `equals`/`hashCode`/`copy()`
- `copy()` called without understanding shallow copy semantics for nested objects
- Mutable properties in data classes used as map keys or set elements
- Data classes without meaningful `equals`/`hashCode` — relying on `Any` defaults
- Exposing internal mutable state through data class constructor parameters

## Good Example

```kotlin
data class User(
    val id: Long,
    val name: String,
    val roles: List<String> = emptyList()
) {
    // Validate immediately in init block
    init {
        require(name.isNotBlank()) { "Name must not be blank" }
    }
}

data class Address(
    val street: String,
    val city: String,
    val postalCode: String
)

// Use copy() for immutability
fun updateEmail(user: User, newEmail: String): User {
    return user.copy(/* ... */)
}
```

## Bad Example

```kotlin
data class User(
    var id: Long,       // var makes it mutable — can change after hash-based collection insert
    var name: String,   // Set or Map key behavior becomes unpredictable
    val roles: MutableList<String> = mutableListOf()  // Mutable collection exposed
)

class Address(  // Should be data class — no equals/hashCode/copy
    val street: String,
    val city: String
)
```
