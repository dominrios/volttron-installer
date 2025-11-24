"""Form state management mixin for React-like form patterns.

This mixin provides a standard form state management pattern that separates
form state from model state, similar to React's controlled components pattern.

Note: In Reflex, state attributes must be defined at the class level.
Subclasses should define form fields as class attributes, and this mixin
provides helper methods to manage them.
"""
import reflex as rx
from typing import Dict, Any, Optional, Callable
from loguru import logger


class FormStateMixin:
    """Mixin for managing form state separately from model state.
    
    This mixin provides:
    - Form field state management
    - Validation state tracking
    - Sync between form state and models
    - Dirty state tracking
    
    Usage:
        class MyState(rx.State, FormStateMixin):
            # Define form fields as class attributes
            form_field1: str = ""
            form_field2: str = ""
            _form_errors: Dict[str, str] = {}
            _form_dirty: Dict[str, bool] = {}
            
            # Define field mapping for sync
            FORM_MAPPING = {
                "form_field1": "model.attribute1",
                "form_field2": "model.attribute2",
            }
    """
    
    def initialize_form_from_model(self, model: Any, field_mapping: Dict[str, str]) -> None:
        """
        Initialize form state from a model.
        
        Args:
            model: The model instance to read from
            field_mapping: Dict mapping form field names to model attribute paths
                          e.g., {"form_host_id": "host.id"}
        """
        if not hasattr(self, '_form_errors'):
            self._form_errors = {}
        if not hasattr(self, '_form_dirty'):
            self._form_dirty = {}
        
        # Build new dicts to trigger reactivity
        new_dirty = {**self._form_dirty}
        new_errors = {**self._form_errors}
        
        for form_field, model_path in field_mapping.items():
            value = self._get_nested_attr(model, model_path)
            if hasattr(self, form_field):
                setattr(self, form_field, value)
            new_dirty[form_field] = False
            new_errors[form_field] = ""
        
        # Reassign to trigger reactivity
        self._form_dirty = new_dirty
        self._form_errors = new_errors
    
    def _get_nested_attr(self, obj: Any, path: str) -> Any:
        """Get nested attribute using dot notation."""
        parts = path.split(".")
        value = obj
        for part in parts:
            if hasattr(value, part):
                value = getattr(value, part)
            elif isinstance(value, dict):
                value = value.get(part)
            else:
                return ""
        return value or ""
    
    def _set_nested_attr(self, obj: Any, path: str, value: Any) -> None:
        """Set nested attribute using dot notation."""
        parts = path.split(".")
        target = obj
        for part in parts[:-1]:
            if hasattr(target, part):
                target = getattr(target, part)
            elif isinstance(target, dict):
                target = target[part]
            else:
                return
        
        final_attr = parts[-1]
        if hasattr(target, final_attr):
            setattr(target, final_attr, value)
        elif isinstance(target, dict):
            target[final_attr] = value
    
    def update_form_field(self, field: str, value: Any, validator: Optional[Callable[[Any], tuple[bool, str]]] = None) -> None:
        """
        Update a form field value.
        
        Args:
            field: Form field name
            value: New value
            validator: Optional validation function that returns (is_valid, error_message)
        """
        if hasattr(self, field):
            setattr(self, field, value)
        
        if not hasattr(self, '_form_dirty'):
            self._form_dirty = {}
        if not hasattr(self, '_form_errors'):
            self._form_errors = {}
        
        # Update dirty state (reassign dict to trigger reactivity)
        self._form_dirty = {**self._form_dirty, field: True}
        
        # Validate and update errors (reassign dict to trigger reactivity)
        if validator:
            is_valid, error_msg = validator(value)
            self._form_errors = {**self._form_errors, field: "" if is_valid else error_msg}
        else:
            self._form_errors = {**self._form_errors, field: ""}
    
    def sync_form_to_model(self, model: Any, field_mapping: Dict[str, str]) -> None:
        """
        Sync form state to model.
        
        Args:
            model: The model instance to update
            field_mapping: Dict mapping form field names to model attribute paths
        """
        for form_field, model_path in field_mapping.items():
            if hasattr(self, form_field):
                value = getattr(self, form_field)
                self._set_nested_attr(model, model_path, value)
    
    def sync_model_to_form(self, model: Any, field_mapping: Dict[str, str]) -> None:
        """
        Sync model state to form (for reverting changes).
        
        Args:
            model: The model instance to read from
            field_mapping: Dict mapping form field names to model attribute paths
        """
        if not hasattr(self, '_form_dirty'):
            self._form_dirty = {}
        if not hasattr(self, '_form_errors'):
            self._form_errors = {}
        
        # Build new dicts to trigger reactivity
        new_dirty = {**self._form_dirty}
        new_errors = {**self._form_errors}
        
        for form_field, model_path in field_mapping.items():
            value = self._get_nested_attr(model, model_path)
            if hasattr(self, form_field):
                setattr(self, form_field, value)
            new_dirty[form_field] = False
            new_errors[form_field] = ""
        
        # Reassign to trigger reactivity
        self._form_dirty = new_dirty
        self._form_errors = new_errors
    
    def get_form_field(self, field: str, default: Any = "") -> Any:
        """Get form field value."""
        if hasattr(self, field):
            return getattr(self, field)
        return default
    
    def get_form_error(self, field: str) -> str:
        """Get form field error message."""
        if not hasattr(self, '_form_errors'):
            return ""
        return self._form_errors.get(field, "")
    
    def is_form_field_dirty(self, field: str) -> bool:
        """Check if form field has been modified."""
        if not hasattr(self, '_form_dirty'):
            return False
        return self._form_dirty.get(field, False)
    
    def is_form_dirty(self) -> bool:
        """Check if any form field has been modified."""
        if not hasattr(self, '_form_dirty'):
            return False
        return any(self._form_dirty.values())
    
    def is_form_valid(self) -> bool:
        """Check if form has no validation errors."""
        if not hasattr(self, '_form_errors'):
            return True
        return not any(self._form_errors.values())
    
    def reset_form(self, field_mapping: Dict[str, str]) -> None:
        """Reset form state."""
        if not hasattr(self, '_form_errors'):
            self._form_errors = {}
        if not hasattr(self, '_form_dirty'):
            self._form_dirty = {}
        
        # Build new dicts to trigger reactivity
        new_dirty = {**self._form_dirty}
        new_errors = {**self._form_errors}
        
        for form_field in field_mapping.keys():
            if hasattr(self, form_field):
                setattr(self, form_field, "")
            new_errors[form_field] = ""
            new_dirty[form_field] = False
        
        # Reassign to trigger reactivity
        self._form_dirty = new_dirty
        self._form_errors = new_errors

