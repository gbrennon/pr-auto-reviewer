---
id: python-async-await
language: python
priority: 60
category: concurrency
---

# Python Async/Await Review

Review the following code for proper async/await usage:

```python
{{ code }}
```

## Checks

- `asyncio.run()` called inside an already-running event loop
- Blocking I/O calls (`open()`, `requests.get()`) inside async functions
- Missing `await` on coroutine calls (coroutine was never awaited)
- Fire-and-forget tasks without error handling (`task = asyncio.create_task(...)`)
- Mixing `asyncio` with `concurrent.futures` without `run_in_executor()`

## Good Example

```python
import asyncio
import aiohttp

async def fetch_url(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

## Bad Example

```python
async def bad_fetch(url: str) -> dict:
    import requests
    # Blocking call inside async function!
    return requests.get(url).json()
```
