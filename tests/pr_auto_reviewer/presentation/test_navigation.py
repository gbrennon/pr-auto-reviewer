import pytest
from textual.app import App, ComposeResult

from pr_auto_reviewer.presentation.navigation import NavigationInput, NavigationMode


class NavigationTestApp(App[None]):
    def __init__(self, mode: NavigationMode) -> None:
        super().__init__()
        self.mode = mode

    def compose(self) -> ComposeResult:
        yield NavigationInput(value="abcd", mode=self.mode, id="input")
        yield NavigationInput(value="efgh", mode=self.mode, id="second")


class TestNavigationInput:
    @pytest.mark.asyncio
    async def test_vim_uses_hjkl_in_normal_mode_and_i_for_insert(self) -> None:
        async with NavigationTestApp(NavigationMode.VIM).run_test() as pilot:
            input_widget = pilot.app.query_one("#input", NavigationInput)
            input_widget.focus()
            input_widget.cursor_position = 2

            await pilot.press("h")
            assert input_widget.cursor_position == 1
            await pilot.press("i")
            await pilot.press("x")
            assert input_widget.value == "axbcd"
            await pilot.press("escape")
            await pilot.press("right")
            assert input_widget.cursor_position == 2

    @pytest.mark.asyncio
    async def test_emacs_supports_control_character_and_arrow_motions(self) -> None:
        async with NavigationTestApp(NavigationMode.EMACS).run_test() as pilot:
            input_widget = pilot.app.query_one("#input", NavigationInput)
            input_widget.focus()
            input_widget.cursor_position = 2

            await pilot.press("ctrl+b")
            assert input_widget.cursor_position == 1
            await pilot.press("ctrl+f")
            assert input_widget.cursor_position == 2
            await pilot.press("left")
            assert input_widget.cursor_position == 1

    @pytest.mark.asyncio
    async def test_arrows_mode_keeps_standard_input_behavior(self) -> None:
        async with NavigationTestApp(NavigationMode.ARROWS).run_test() as pilot:
            input_widget = pilot.app.query_one("#input", NavigationInput)
            input_widget.focus()
            input_widget.cursor_position = 2

            await pilot.press("left")
            assert input_widget.cursor_position == 1
            await pilot.press("h")
            assert input_widget.value == "ahbcd"
