---
id: kotlin-coroutines
language: kotlin
priority: 85
category: concurrency
---

# Kotlin Coroutines Review

Review the following Kotlin code for proper coroutine usage:

```kotlin
{{ code }}
```

## Checks

- `GlobalScope.launch` or `GlobalScope.async` — coroutines never cancelled, may leak
- Blocking calls (`Thread.sleep()`, I/O) inside coroutine without `Dispatchers.IO`
- Missing `supervisorScope` where child failure should not cancel siblings
- `async {}` without corresponding `await()` — fire-and-forget, exceptions lost
- Not passing `CoroutineScope` explicitly — using implicit receivers unsafely
- `runBlocking` in a suspend function or on the main thread
- Missing cancellation checks in long-running loops (`isActive` or `ensureActive()`)
- Launching coroutines without structured concurrency (no parent scope)

## Good Example

```kotlin
class UserRepository(private val db: Database) {

    suspend fun findUsers(ids: List<Long>): List<User> = coroutineScope {
        ids.map { id ->
            async(Dispatchers.IO) {
                db.query("SELECT * FROM users WHERE id = ?", id)
            }
        }.awaitAll()
    }

    suspend fun processBatch(items: List<Item>) = coroutineScope {
        items.forEach { item ->
            launch {
                if (!isActive) return@launch  // Respect cancellation
                processItem(item)
            }
        }
    }
}
```

## Bad Example

```kotlin
class UserRepository {

    fun findUsers(ids: List<Long>): List<User> {
        return runBlocking {  // Blocks thread — never use in suspend context
            ids.map { id ->
                GlobalScope.async {  // Leaked coroutine, no cancellation
                    Thread.sleep(1000)  // Blocking in coroutine
                    db.query("...")
                }
            }.map { it.await() }
        }
    }
}
```
