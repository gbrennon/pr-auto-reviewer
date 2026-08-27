from ._helpers import *


class TestTemplateWiringContract:
    """Templates fail fast on incomplete wiring via StrictUndefined."""

    def test_missing_context_variable_raises(self) -> None:
        with pytest.raises(jinja2.exceptions.UndefinedError):
            InitialUserMessageRenderer().render(file_listing="only-files.j2")

