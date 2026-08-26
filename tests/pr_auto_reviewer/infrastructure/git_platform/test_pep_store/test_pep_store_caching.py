from ._helpers import *


class TestPepStoreCaching:

    def test_fetches_only_once(self):
        call_count = 0

        def counting_get(url: str) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return dict(_SAMPLE_PEPS)

        store = PepStore(http_get=counting_get)
        store.guidance("3.9")
        store.guidance("3.10")
        assert call_count == 1

