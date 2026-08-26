from ._helpers import *


class TestClientMetadata:
    """Exercises the client accessor properties."""

    def test_model_property_returns_model(self) -> None:
        assert _client(model="code-review:latest").model == "code-review:latest"

    def test_host_property_strips_trailing_slash(self) -> None:
        assert _client(host="http://localhost:11434/").host == "http://localhost:11434"

    def test_json_schema_is_object(self) -> None:
        assert _client().json_schema["type"] == "object"

