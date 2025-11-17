"""
DEPRECATED: This file is kept for backward compatibility.

All state classes have been moved to the states/ directory:
- AppState -> states/app_state.py
- ToolState -> states/tool_state.py
- SettingsState -> states/settings_state.py
- PlatformPageState -> states/platform/platform_page_state.py
- AgentConfigState -> states/platform/agent_config_state.py
- IndexPageState -> states/index_state.py
- BacnetScanState -> states/bacnet/bacnet_scan_state.py

Please update your imports to use:
    from volttron_installer.states import AppState, ToolState, ...
"""

# Re-export all states for backward compatibility
from .states import (
    AppState,
    ToolState,
    SettingsState,
    IndexPageState,
    PlatformPageState,
    AgentConfigState,
    BacnetScanState,
)

__all__ = [
    "AppState",
    "ToolState",
    "SettingsState",
    "IndexPageState",
    "PlatformPageState",
    "AgentConfigState",
    "BacnetScanState",
]
