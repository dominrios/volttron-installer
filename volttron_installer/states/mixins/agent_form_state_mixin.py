"""Agent form state management mixin following FormStateMixin patterns."""
import reflex as rx
from typing import Any, Dict
import re
from .form_state_mixin import FormStateMixin
from ...services.validation_service import ValidationService
from ...utils.validate_content import check_json, check_yaml


class AgentFormStateMixin(FormStateMixin):
    """Mixin class for agent form state management.
    
    Extends FormStateMixin to provide agent-specific form state management
    following the same patterns as PlatformPageState.
    """
    
    # Form fields
    form_agent_identity: str = ""
    form_agent_source: str = ""
    form_agent_config: str = "{}"
    
    # Form validation state (inherited from FormStateMixin but can be overridden)
    _form_initialized: bool = False
    _form_errors: Dict[str, str] = {}
    _form_dirty: Dict[str, bool] = {}
    
    # Field mapping between form and model
    AGENT_FORM_MAPPING = {
        "form_agent_identity": "identity",
        "form_agent_source": "source",
        "form_agent_config": "config",
    }
    
    @rx.var
    def form_initialized(self) -> bool:
        """Check if form has been initialized."""
        return self._form_initialized
    
    @rx.var
    def has_form_errors(self) -> bool:
        """Check if there are any form errors."""
        return not self.is_form_valid()
    
    @rx.var
    def form_error_agent_identity(self) -> str:
        """Get form error for agent_identity field."""
        return self.get_form_error("form_agent_identity")
    
    @rx.var
    def form_error_agent_source(self) -> str:
        """Get form error for agent_source field."""
        return self.get_form_error("form_agent_source")
    
    @rx.var
    def form_error_agent_config(self) -> str:
        """Get form error for agent_config field."""
        return self.get_form_error("form_agent_config")
    
    def initialize_agent_form(self, agent_model: Any = None):
        """
        Initialize form fields from agent model.
        
        Args:
            agent_model: The agent model instance to read from
        """
        if agent_model:
            # Use FormStateMixin's initialize_form_from_model method
            self.initialize_form_from_model(agent_model, self.AGENT_FORM_MAPPING)
        
        self._form_initialized = True
    
    def update_form_agent_field(self, field: str, value: str):
        """
        Update agent form field with validation.
        
        Args:
            field: Field name without "form_" prefix (e.g., "agent_identity")
            value: New value
        """
        # Map field names to form fields
        field_mapping = {
            "agent_identity": "form_agent_identity",
            "agent_source": "form_agent_source",
            "agent_config": "form_agent_config",
        }
        
        form_field = field_mapping.get(field, f"form_{field}")
        
        # Get appropriate validator
        validators = {
            "agent_identity": lambda v: AgentFormStateMixin._validate_agent_identity(v),
            "agent_source": lambda v: ValidationService.validate_required(v, "Agent source"),
            "agent_config": lambda v: AgentFormStateMixin._validate_agent_config(v),
        }
        
        validator = validators.get(field)
        if validator:
            self.update_form_field(form_field, value, validator)
        else:
            self.update_form_field(form_field, value)
    
    @staticmethod
    def _validate_agent_identity(value: str) -> tuple[bool, str]:
        """
        Validate agent identity.
        
        Args:
            value: The identity value to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value or not value.strip():
            return False, "Agent identity is required"
        
        # Allow letters, numbers, underscores, and hyphens
        pattern = r'^[a-zA-Z0-9_-]+$'
        if not re.match(pattern, value):
            return False, "Identity can only contain letters, numbers, underscores and hyphens"
        
        return True, ""
    
    @staticmethod
    def _validate_agent_config(value: str) -> tuple[bool, str]:
        """
        Validate agent config JSON or YAML.
        
        Args:
            value: The config JSON or YAML string to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value or not value.strip():
            return True, ""  # Empty config is valid (will be treated as {})
        
        # Try JSON first
        if check_json(value):
            return True, ""
        
        # Try YAML if JSON fails
        if check_yaml(value):
            return True, ""
        
        # Neither JSON nor YAML is valid
        return False, "Invalid configuration: must be valid JSON or YAML"
    
    def sync_agent_form_to_model(self, agent_model: Any) -> None:
        """
        Sync form state to agent model.
        
        Args:
            agent_model: The agent model instance to update
        """
        self.sync_form_to_model(agent_model, self.AGENT_FORM_MAPPING)
    
    def sync_agent_model_to_form(self, agent_model: Any) -> None:
        """
        Sync agent model state to form (for reverting changes).
        
        Args:
            agent_model: The agent model instance to read from
        """
        self.sync_model_to_form(agent_model, self.AGENT_FORM_MAPPING)
    
    def get_form_data(self) -> dict:
        """Get form data as a dictionary."""
        return {
            "identity": self.form_agent_identity,
            "source": self.form_agent_source,
            "config": self.form_agent_config,
        }