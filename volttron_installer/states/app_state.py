"""Application-level state management."""
import reflex as rx
from loguru import logger
from ..navigation.state import NavigationState


class AppState(rx.State):
    """The app state."""
    _sidebar_page_selected: str = "overview"
    tool_accordion_value: str = "tools"

    # Events
    @rx.var
    def sidebar_selected_page(self) -> str:
        self._sidebar_page_selected = self.router.page.raw_path if self.router.page.raw_path != "/" else "overview"
        logger.debug(self._sidebar_page_selected)
        return self._sidebar_page_selected

    @rx.event
    def toggle_tool_dropdown(self, value: str):
        """Toggle the tool dropdown."""
        self.tool_accordion_value = value

    @rx.event
    def select_bacnet_scan(self):
        self.sidebar_page_selected = "bacnet_scan"
        # yield NavigationState.route_to_bacnet_scan()

    @rx.event
    def select_overview(self):
        self.sidebar_page_selected = "overview"
        # yield NavigationState.route_to_index()

