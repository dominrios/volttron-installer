"""State for managing tool lifecycle."""
import reflex as rx
from loguru import logger
from typing import Optional
import asyncio
from ..backend.models import ToolRequest
from ..thin_endpoint_wrappers import tool_status, start_tool, stop_tool, ToolStatusResponse


class ToolState(rx.State):
    """State for managing tool lifecycle."""
    
    # Track running tools
    _running_tools: dict[str, bool] = {}
    loading_tools: dict[str, bool] = {}
    error_message: Optional[str] = None
    
    # Tool configuration
    tool_configs: dict[str, ToolRequest] = {
        "bacnet_scan_tool": ToolRequest(
            tool_name="bacnet_scan_tool",
            module_path="bacnet_scan_tool.main:app",
        ),
        # Add other tools as we go
    }

    # Computed var to make sure we are accessing running tool
    @rx.var
    def running_tools(self) -> dict[str, bool]:
        return self._running_tools

    @rx.event(background=True)
    async def monitor_all_tools(self):
        while True:
            await asyncio.sleep(5)
            async with self:
                for tool_id in self.tool_configs:
                    try:
                        status = await tool_status(tool_id)
                        self._running_tools[tool_id] = status.tool_running
                    except Exception as e:
                        self._running_tools[tool_id] = False

    @rx.event
    async def start_tool(self, tool_id: str):
        """Start a specific tool service."""
        logger.debug(f"starting tool : {tool_id}")
        if tool_id not in self.tool_configs:
            logger.debug(f"Unknown tool: {tool_id}")
            return
        
        # Check if already running
        if self._running_tools.get(tool_id, False):
            logger.debug("tool is already running")
            return
        
        # Set loading state
        logger.debug(f"setting tool to loading: {tool_id}")
        self.loading_tools[tool_id] = True
        
        try:
            # Get tool config
            config = self.tool_configs[tool_id]
            logger.debug("calling api...")
            # Call API to start the tool
            await start_tool(config)
            self.running_tools[tool_id] = True
            logger.debug("tool started")
            
            yield ToolState.monitor_all_tools()
        except Exception as e:
            logger.debug(f"Error starting tool: {str(e)}")
        finally:
            # Clear loading state
            self.loading_tools[tool_id] = False
    
    @rx.event
    async def stop_tool(self, tool_id: str) -> None:
        """Stop a specific tool service."""
        logger.debug(f"stopping tool : {tool_id}")
        if tool_id not in self.tool_configs:
            logger.debug(f"Unknown tool: {tool_id}")
            return
        
        # Check if it's running
        if not self._running_tools.get(tool_id, False):
            logger.debug("tool is already not running")
            return
        
        # Set loading state
        self.loading_tools[tool_id] = True
        
        try:           
            # Call API to stop the tool
            await stop_tool(tool_id)
            self.running_tools[tool_id] = False
            logger.debug("tool stopped")

        except Exception as e:
            logger.debug(f"Error stopping tool: {str(e)}")
        finally:
            # Clear loading state
            self.loading_tools[tool_id] = False
    
    @rx.event
    async def check_tool_status(self, tool_id: str) -> None:
        """Check if a specific tool is running."""
        if tool_id not in self.tool_configs:
            return
        
        try:
            # Call API to get tool status
            tool_status_response: ToolStatusResponse = await tool_status(tool_id)
            self.running_tools[tool_id] = tool_status_response.tool_running
        except Exception as e:
            logger.debug(f"Error checking tool status: {str(e)}")

    @classmethod
    async def is_tool_running(cls, tool_name: str) -> bool:
        try:
            response: ToolStatusResponse = await tool_status(tool_name)
            return response.tool_running
        except Exception as e:
            logger.debug(f"There was an error checking the tool status for `{tool_name}: {e}`")
            return False

