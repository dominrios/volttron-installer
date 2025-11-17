"""Settings state management."""
import reflex as rx
from ..settings import get_settings

settings = get_settings()


class SettingsState(rx.State):
    """The settings state."""

    app_name: str = settings.app_name
    secret_key: str = settings.secret_key

    _upload_dir: str = settings.upload_dir
    _data_dir: str = settings.data_dir

