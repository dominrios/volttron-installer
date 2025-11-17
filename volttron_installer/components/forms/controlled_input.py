"""Controlled input component for React-like form patterns."""
import reflex as rx
from typing import Optional, Callable, Any


def ControlledInput(
    state: Any,
    field_name: str,
    placeholder: str = "",
    label: str = "",
    input_type: str = "text",
    on_change: Optional[Callable] = None,
    on_blur: Optional[Callable] = None,
    validation: Optional[Callable[[str], tuple[bool, str]]] = None,
    **kwargs
) -> rx.Component:
    """
    Controlled input component that manages its own state.
    
    This component follows React's controlled component pattern where:
    - The value is always controlled by state
    - Changes are handled through callbacks
    - Validation can be applied on change or blur
    
    Args:
        state: State instance with form management methods
        field_name: Name of the form field
        placeholder: Input placeholder text
        label: Label text for the input
        input_type: HTML input type (text, number, email, etc.)
        on_change: Optional callback for change events
        on_blur: Optional callback for blur events
        validation: Optional validation function (value) -> (is_valid, error_message)
        **kwargs: Additional props to pass to rx.input
        
    Returns:
        rx.Component: A controlled input component
    """
    # Use direct attribute access for Reflex reactivity
    # Reflex will handle reactivity through state attribute access
    value = getattr(state, field_name, "") if hasattr(state, field_name) else ""
    # Error access - will be reactive through state
    error_attr = getattr(state, '_form_errors', {}) if hasattr(state, '_form_errors') else {}
    error = error_attr.get(field_name, "") if isinstance(error_attr, dict) else ""
    
    def handle_change(value: str):
        """Handle input change."""
        if hasattr(state, 'update_form_field'):
            state.update_form_field(field_name, value, validation)
        if on_change:
            on_change(value)
    
    def handle_blur():
        """Handle input blur."""
        if on_blur:
            on_blur()
    
    return rx.vstack(
        rx.cond(
            label != "",
            rx.text(label, size="2", weight="medium"),
        ),
        rx.input(
            value=value,
            placeholder=placeholder,
            type=input_type,
            on_change=handle_change,
            on_blur=handle_blur,
            **kwargs
        ),
        rx.cond(
            error != "",
            rx.text(error, size="1", color="red"),
        ),
        spacing="1",
        width="100%",
    )

