# volttron_installer/stores/config_store_form.py
from typing import Any, Literal, Optional
import reflex as rx
from ..model_views import ConfigStoreEntryModelView

class ConfigStoreFormState(rx.State):
    """Form state for ConfigStoreEntry."""
    
    # Form fields
    path: str = ""
    data_type: Literal["CSV", "JSON"] = "JSON"
    value: str = ""
    selected_variant: str = "Custom"
    selected_cell: str = ""
    
    # Form state
    is_loading: bool = False
    is_submitting: bool = False
    error_message: str = ""
    
    # Reference to the original model (if editing)
    _original_model: Optional[ConfigStoreEntryModelView] = None
    
    def load_from_model(self, model: ConfigStoreEntryModelView):
        """Load form data from model."""
        self._original_model = model
        self.path = model.path
        self.data_type = model.data_type
        self.value = model.value
        self.selected_variant = model.selected_variant
        self.selected_cell = model.selected_cell or ""
    
    def validate_form(self) -> bool:
        """Validate form data."""
        if not self.path.strip():
            self.error_message = "Path is required"
            return False
        if not self.value.strip() and self.data_type == "JSON":
            self.error_message = "Value is required for JSON"
            return False
        return True
    
    async def handle_submit(self):
        """Handle form submission."""
        self.is_submitting = True
        self.error_message = ""
        
        if not self.validate_form():
            self.is_submitting = False
            return
            
        try:
            # Create or update the model
            if self._original_model:
                # Update existing
                model = self._original_model
                model.path = self.path
                model.data_type = self.data_type
                model.value = self.value
                model.selected_variant = self.selected_variant
                model.changed = True
            else:
                # Create new
                model = ConfigStoreEntryModelView(
                    path=self.path,
                    data_type=self.data_type,
                    value=self.value,
                    selected_variant=self.selected_variant,
                    changed=True
                )
            
            # Save the model (you'll need to implement this in your state)
            # await self.save_config_store_entry(model)
            
            # Reset form on success
            self.reset_form()
            return rx.redirect("/config-store")  # or wherever you want to go
            
        except Exception as e:
            self.error_message = f"Error saving configuration: {str(e)}"
        finally:
            self.is_submitting = False
    
    def reset_form(self):
        """Reset the form to its initial state."""
        self.path = ""
        self.data_type = "JSON"
        self.value = ""
        self.selected_variant = "Custom"
        self.selected_cell = ""
        self._original_model = None
        self.error_message = ""