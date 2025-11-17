"""Service for Instance business logic."""
from loguru import logger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Instance


class InstanceService:
    """Service class containing business logic for Instance models."""
    
    @staticmethod
    def has_uncaught_changes(instance: "Instance") -> bool:
        """
        Check if the instance has uncaught changes.
        
        Args:
            instance: The Instance to check
            
        Returns:
            True if the host has changed from its safe state, False otherwise
        """
        return instance.host.to_dict() != instance.safe_host_entry
    
    @staticmethod
    def does_host_have_errors(instance: "Instance") -> bool:
        """
        Check if the host has validation errors.
        
        Args:
            instance: The Instance to check
            
        Returns:
            True if host has errors (missing required fields), False otherwise
            
        Note:
            This method returns True when fields are missing (has errors).
            The original implementation had inverted logic but this version
            corrects it to match the method name and expected behavior.
        """
        host_dict = instance.host.to_dict()
        
        # Check if required fields are missing
        has_errors = not (
            host_dict.get("id") and 
            host_dict.get("ansible_user") and 
            host_dict.get("ansible_host") != ""
        )
        
        if has_errors:
            logger.debug(f"Error: Missing host details {host_dict}")
        
        return has_errors
    
    @staticmethod
    def refresh_for_copy(instance: "Instance") -> None:
        """
        Refresh the instance for copying.
        
        Resets the instance state to prepare it for being copied.
        This includes resetting flags, clearing deployment state, and
        resetting agent configurations.
        
        Args:
            instance: The Instance to refresh
        """
        instance.new_instance = True
        instance.platform.in_file = False
        instance.deployed = False
        instance.password = ""
        
        for agent in instance.platform.agents.values():
            agent.in_file = False
            agent.selected_config_component_id = ""
            agent.selected_agent_config_tab = "1"
            for config in agent.config_store:
                config.in_file = False
                config.selected_cell = ""

