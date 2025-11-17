"""Form field wrapper component."""
import reflex as rx
from typing import Optional, Any


def FormField(
    label: str,
    input_component: rx.Component,
    error_message: Optional[str] = None,
    required: bool = False,
    help_text: Optional[str] = None,
) -> rx.Component:
    """
    Form field wrapper that provides consistent styling and error display.
    
    Args:
        label: Field label
        input_component: The input component to wrap
        error_message: Optional error message to display
        required: Whether the field is required
        help_text: Optional help text to display below the input
        
    Returns:
        rx.Component: A form field component
    """
    return rx.vstack(
        rx.hstack(
            rx.text(label, size="2", weight="medium"),
            rx.cond(
                required,
                rx.text("*", color="red", size="2"),
            ),
            spacing="1",
            align="center",
        ),
        input_component,
        rx.cond(
            error_message is not None and error_message != "",
            rx.text(error_message, size="1", color="red"),
        ),
        rx.cond(
            help_text is not None and help_text != "",
            rx.text(help_text, size="1", color="gray"),
        ),
        spacing="1",
        width="100%",
        align="start",
    )

