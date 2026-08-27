from ._helpers import *


class TestPepStoreErrorHandling:

    def test_guidance_handles_fetch_failure(self):
        def failing_get(url: str) -> dict[str, Any]:
            raise RuntimeError("Network error")

        store = PepStore(http_get=failing_get)
        assert store.guidance("3.9") is None

    def test_guidance_handles_invalid_version(self):
        store = _make_store()
        assert store.guidance("not.a.version") is None

