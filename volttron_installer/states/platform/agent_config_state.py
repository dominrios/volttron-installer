"""Agent configuration state management with form-driven approach."""
import reflex as rx
from ...states.mixins.agent_form_state_mixin import AgentFormStateMixin
from ...model_views import AgentModelView, ConfigStoreEntryModelView
from ...utils.create_component_uid import generate_unique_uid
from ...utils.conversion_methods import json_string_to_csv_string, csv_string_to_json_string, identify_string_format, csv_string_to_usable_dict
from ...utils.validate_content import check_json, check_csv, check_path, check_yaml, check_regular_expression
from ...utils.create_csv_string import create_csv_string, create_and_validate_csv_string
from ...services.config_store_service import ConfigStoreService
from ...services.validation_service import ValidationService
from .platform_page_state import PlatformPageState
from .platform_page_state import Instance
import csv, yaml, json, io, re
from loguru import logger
from typing import Optional, Dict
from copy import deepcopy

class AgentConfigState(AgentFormStateMixin, rx.State):
    """State management for agent configuration."""
    
    # Agent form fields (must be declared here for Reflex to recognize them)
    form_agent_identity: str = ""
    form_agent_source: str = ""
    form_agent_config: str = "{}"
    
    # Form validation state
    _form_initialized: bool = False
    _last_initialized_agent_uid: str = ""  # Track which agent we last initialized for
    _form_errors: Dict[str, str] = {}
    _form_dirty: Dict[str, bool] = {}
    
    # Working agent data
    working_agent: AgentModelView = AgentModelView()
    selected_component_id: str = ""
    draft_visible: bool = False
    session_hydrated: bool = False
    
    # Config store form state (for selected entry)
    form_config_path: str = ""
    form_config_data_type: str = "JSON"
    form_config_value: str = ""
    
    @rx.var
    def is_hydrated(self) -> bool:
        """Check if state is hydrated."""
        return self.session_hydrated
    
    @rx.var
    def agent_details(self) -> dict:
        """Get agent details from route parameters."""
        args = self.router.page.params
        return {
            "uid": args.get("uid", ""),
            "agent_uid": args.get("agent_uid", "")
        }
    
    @rx.var
    def selected_tab(self) -> str:
        """Get the currently selected tab."""
        return self.working_agent.selected_agent_config_tab
    
    @rx.var
    def selected_config_entry(self) -> Optional[ConfigStoreEntryModelView]:
        """Get the currently selected config store entry."""
        if not self.working_agent.selected_config_component_id:
            return None
        for entry in self.working_agent.config_store:
            if entry.component_id == self.working_agent.selected_config_component_id:
                return entry
        return None
    
    # Lifecycle methods
    @rx.event
    async def hydrate_working_agent(self):
        """Initialize working agent from platform state."""
        platform_state: PlatformPageState = await self.get_state(PlatformPageState)
        working_platform: Instance = platform_state.platforms.get(self.agent_details["uid"])
        
        if not working_platform:
            logger.error(f"Platform {self.agent_details['uid']} not found")
            return
        
        # Find agent by routing_id
        current_agent_uid = self.agent_details["agent_uid"]
        for agent in working_platform.platform.agents.values():
            if agent.routing_id == current_agent_uid:
                self.working_agent = agent
                break
        
        # Always re-initialize form from model if:
        # 1. Form was never initialized, OR
        # 2. We're viewing a different agent than last time
        # This ensures form state always reflects the current agent model
        if not self._form_initialized or self._last_initialized_agent_uid != current_agent_uid:
            self.initialize_agent_form(self.working_agent)
            self._last_initialized_agent_uid = current_agent_uid
        
        self.session_hydrated = True
    
    # Agent configuration methods
    @rx.event
    async def save_agent_config(self):
        """Save the agent configuration using form state."""
        # Validate form first
        if not self.is_form_valid():
            yield rx.toast.error("Please fix form errors before saving")
            return
        
        # Check if identity is already in use
        platform_state: PlatformPageState = await self.get_state(PlatformPageState)
        working_platform: Instance = platform_state.platforms.get(self.agent_details["uid"])
        
        if working_platform:
            registered_identities = [
                agent.identity for identity, agent in working_platform.platform.agents.items()
                if agent.routing_id != self.working_agent.routing_id
            ]
            if self.form_agent_identity in registered_identities:
                yield rx.toast.error("Identity is already in use!")
                return
        
        # Sync form state to model
        self.sync_agent_form_to_model(self.working_agent)
        
        # Mark agent as saved
        self.working_agent.is_new = False
        self.working_agent.safe_agent = self.working_agent.to_dict()
        
        # Reset form dirty state
        for field in self.AGENT_FORM_MAPPING.keys():
            self._form_dirty[field] = False
        
        yield rx.toast.success("Agent configuration saved")
        self.draft_visible = False
    
    @rx.event
    def update_agent_detail(self, field: str, value: str):
        """Update agent detail using form state."""
        # Map field names to form fields
        field_mapping = {
            "identity": "agent_identity",
            "source": "agent_source",
            "config": "agent_config",
        }
        
        form_field = field_mapping.get(field)
        if form_field:
            self.update_form_agent_field(form_field, value)
    
    @rx.event
    def update_form_agent_field(self, field: str, value: str):
        """Update agent form field with validation (event handler wrapper)."""
        # Call the mixin method to update form state
        AgentFormStateMixin.update_form_agent_field(self, field, value)
        # Sync form to model immediately to preserve changes across navigation
        # This ensures unsaved form data is preserved in the model
        # Only sync if we have a valid working agent (hydration complete)
        if self.session_hydrated and self.working_agent and hasattr(self.working_agent, 'routing_id') and self.working_agent.routing_id:
            self.sync_agent_form_to_model(self.working_agent)
    
    @rx.event
    async def handle_agent_config_upload(self, files: list[rx.UploadFile]):
        """Handle agent config file upload."""
        if not files:
            return
        
        file = files[0]
        upload_data = await file.read()
        outfile = rx.get_upload_dir() / file.filename
        
        with outfile.open("wb") as file_object:
            file_object.write(upload_data)
        
        result: str = ""
        
        if file.filename.endswith('.json'):
            with open(outfile, 'r') as file_object:
                data = json.load(file_object)
                result = json.dumps(data, indent=4)
        elif file.filename.endswith('.yaml') or file.filename.endswith('.yml'):
            with open(outfile, 'r') as file_object:
                data = yaml.safe_load(file_object)
                result = yaml.dump(data, sort_keys=False, default_flow_style=False)
        else:
            yield rx.toast.error("Unsupported file format")
            return
        
        # Update form state
        self.update_form_agent_field("agent_config", result)
        yield rx.toast.success("Config uploaded successfully")
    
    # Config store methods
    @rx.event
    def create_blank_config_entry(self):
        """Create a new blank config store entry."""
        new_component_id = generate_unique_uid()
        blank_config = ConfigStoreEntryModelView(
            path="",
            data_type="JSON",
            value="",
            component_id=new_component_id,
            safe_entry={
                "path": "",
                "data_type": "JSON",
                "value": "",
                "component_id": new_component_id
            }
        )
        blank_config.safe_entry = blank_config.dict()
        self.working_agent.config_store.append(blank_config)
        self.set_component_id(new_component_id)
    
    @rx.event
    async def handle_config_store_entry_upload(self, files: list[rx.UploadFile]):
        """Handle config store entry file upload."""
        if not files:
            return
        
        current_file = files[0]
        upload_data = await current_file.read()
        outfile = rx.get_upload_dir() / current_file.filename
        
        with outfile.open("wb") as file_object:
            file_object.write(upload_data)
        
        result: str = ""
        file_type: str = ""
        
        if current_file.filename.endswith('.json'):
            with open(outfile, 'r') as file_object:
                data = json.load(file_object)
                file_type = "JSON"
                result = json.dumps(data, indent=4)
        elif current_file.filename.endswith('.csv'):
            with open(outfile, 'r') as file_object:
                reader = csv.reader(file_object)
                output = io.StringIO()
                writer = csv.writer(output)
                for row in reader:
                    writer.writerow(row)
                file_type = "CSV"
                result = output.getvalue()
                output.close()
        else:
            yield rx.toast.error("Unsupported file format")
            return
        
        # Create new config entry from uploaded file
        new_config_entry = ConfigStoreEntryModelView(
            path="",
            data_type=file_type,
            value=result,
            component_id=generate_unique_uid()
        )
        
        if file_type == "CSV":
            usable_csv = csv_string_to_usable_dict(result)
            new_config_entry.csv_variants["Custom"] = usable_csv
        
        new_config_entry.safe_entry = new_config_entry.dict()
        self.working_agent.config_store.append(new_config_entry)
        self.set_component_id(new_config_entry.component_id)
        yield rx.toast.success("Config store entry uploaded successfully")
    
    @rx.event
    def delete_config_store_entry(self, config: ConfigStoreEntryModelView):
        """Delete a config store entry."""
        for index, entry in enumerate(self.working_agent.config_store):
            if entry.component_id == config.component_id:
                self.working_agent.config_store.pop(index)
                if self.working_agent.selected_config_component_id == config.component_id:
                    self.set_component_id("")
                yield rx.toast.info(f"Config store entry '{config.path}' has been removed")
                return
    
    @rx.event
    def set_component_id(self, component_id: str):
        """Set the selected config component ID."""
        if self.working_agent.selected_config_component_id == component_id:
            self.working_agent.selected_config_component_id = ""
            # Clear form state when deselecting
            self.form_config_path = ""
            self.form_config_data_type = "JSON"
            self.form_config_value = ""
        else:
            self.working_agent.selected_config_component_id = component_id
            # Initialize form state from selected entry
            entry = self.selected_config_entry
            if entry:
                self.form_config_path = entry.path
                self.form_config_data_type = entry.data_type
                self.form_config_value = entry.value
    
    @rx.event
    def update_config_detail(self, field: str, value: str):
        """Update config store entry detail using form state."""
        entry = self.selected_config_entry
        if not entry:
            return
        
        # Update form state first
        if field == "path":
            self.form_config_path = value
        elif field == "data_type":
            # Handle data type conversion using form state
            current_value = self.form_config_value
            if current_value == "":
                self.form_config_data_type = value
            else:
                # If switching from CSV to JSON, convert from csv_variants if available
                # (to capture any unsaved edits made through the CSV table)
                if self.form_config_data_type == "CSV" and value == "JSON":
                    # Try to convert from csv_variants first (most up-to-date)
                    try:
                        working_dict = entry.csv_variants.get(entry.selected_variant, {})
                        if working_dict:
                            headers = list(working_dict.keys())
                            rows = [[working_dict[header][i] for header in headers] for i in range(10)]
                            csv_string = create_csv_string(headers, rows)
                            json_string = csv_string_to_json_string(csv_string)
                        else:
                            # Fall back to form_config_value
                            json_string = csv_string_to_json_string(current_value)
                    except Exception:
                        # Fall back to form_config_value
                        json_string = csv_string_to_json_string(current_value)
                    self.form_config_data_type = value
                    self.form_config_value = json_string
                elif self.form_config_data_type == "JSON" and value == "CSV":
                    csv_string = json_string_to_csv_string(current_value)
                    usable_csv = csv_string_to_usable_dict(csv_string)
                    entry.csv_variants["Custom"] = usable_csv
                    entry.selected_variant = "Custom"
                    self.form_config_data_type = value
                    # Keep form_config_value as CSV string for consistency
                    self.form_config_value = csv_string
                else:
                    # Same type, just update
                    self.form_config_data_type = value
        elif field == "value":
            self.form_config_value = value
        
        # Sync form state to model immediately for reactivity
        entry.path = self.form_config_path
        entry.data_type = self.form_config_data_type
        entry.value = self.form_config_value
        
        # Validate and update entry state using form state
        valid, validity_map = self.validate_config_entry_from_form_state(entry)
        entry.valid = valid
        entry.changed = entry.dict() != entry.safe_entry
    
    @rx.event
    def save_config_store_entry(self, config: ConfigStoreEntryModelView):
        """Save a config store entry by syncing form state to model first."""
        # Sync form state to model before saving
        entry = self.selected_config_entry
        if not entry or entry.component_id != config.component_id:
            yield rx.toast.error("No config entry selected")
            return
        
        # Sync form state to model
        entry.path = self.form_config_path
        entry.data_type = self.form_config_data_type
        entry.value = self.form_config_value
        
        committable: bool = True
        
        # Check for duplicate paths
        list_of_config_paths = [
            (entry.safe_entry.get("path", ""), entry.component_id)
            for entry in self.working_agent.config_store
            if entry.safe_entry.get("path", "") != ""
        ]
        
        for path, component_id in list_of_config_paths:
            if entry.path == "" or (entry.path == path and entry.component_id != component_id):
                committable = False
                yield rx.toast.error("Config path is already in use")
                return
        
        # Validate using ConfigStoreService
        valid, errors = ConfigStoreService.validate_entry_model_view(entry)
        if not valid:
            committable = False
            for error_msg in errors.values():
                yield rx.toast.error(error_msg)
            return
        
        # Handle CSV conversion if needed
        if entry.data_type == "CSV" and committable:
            try:
                working_dict = entry.csv_variants[entry.selected_variant]
                headers = list(working_dict.keys())
                rows = [[working_dict[header][i] for header in headers] for i in range(10)]
                csv_string = create_csv_string(headers, rows)
                
                if not check_csv(csv_string):
                    raise ValueError("CSV String is not valid")
                
                entry.value = csv_string
                entry.csv_header_row = headers
                entry.formatted_csv = rows
                # Update form state with the converted CSV string
                self.form_config_value = csv_string
            except Exception as e:
                logger.debug(f"CSV validation error: {e}")
                committable = False
                yield rx.toast.error("CSV variant is not valid")
        
        if not committable:
            return
        
        # Save the entry
        entry.safe_entry = entry.dict()
        entry.uncommitted = False
        
        # Update in config_store
        for i, store_entry in enumerate(self.working_agent.config_store):
            if store_entry.component_id == entry.component_id:
                self.working_agent.config_store[i] = entry
                break
        
        yield rx.toast.success("Config saved successfully")
    
    @rx.event
    def change_agent_config_tab(self, value: str):
        """Change the agent config tab."""
        self.working_agent.selected_agent_config_tab = value
    
    @rx.event
    def flip_draft_visibility(self):
        """Toggle draft dialog visibility."""
        self.draft_visible = not self.draft_visible
    
    @rx.event
    def handle_unsaved_config_banner_click(self, component_id: str):
        """Handle click on unsaved config banner."""
        self.set_component_id(component_id)
    
    # Validation methods
    @rx.var
    def agent_valid(self) -> bool:
        """Check if agent is valid using form state."""
        return self.is_form_valid() and self.agent_identity_not_in_use
    
    @rx.var
    def agent_identity_not_in_use(self) -> bool:
        """Check if agent identity is not in use.
        
        Note: Full validation happens in save_agent_config.
        This is a placeholder that always returns True for UI purposes.
        """
        return True
    
    @rx.var
    def agent_identity_validity(self) -> bool:
        """Check agent identity validity using form state."""
        return self.form_error_agent_identity == ""
    
    @rx.var
    def agent_source_validity(self) -> bool:
        """Check agent source validity using form state."""
        return self.form_error_agent_source == ""
    
    @rx.var
    def agent_config_validity(self) -> bool:
        """Check agent config validity using form state."""
        return self.form_error_agent_config == ""
    
    @rx.var
    def path_validity(self) -> bool:
        """Check path validity for selected config entry using form state."""
        if not self.working_agent.selected_config_component_id:
            return True
        valid, _ = ConfigStoreService.validate_path(self.form_config_path)
        return valid
    
    @rx.var
    def config_json_validity(self) -> bool:
        """Check JSON validity for selected config entry using form state."""
        if not self.working_agent.selected_config_component_id or self.form_config_data_type != "JSON":
            return True
        valid, _ = ConfigStoreService.validate_json_value(self.form_config_value)
        return valid
    
    @rx.var
    def check_csv_validity(self) -> bool:
        """Check CSV validity for selected config entry using form state."""
        if not self.working_agent.selected_config_component_id or self.form_config_data_type != "CSV":
            return True
        valid, _ = ConfigStoreService.validate_csv_value(self.form_config_value)
        return valid
    
    @rx.var
    def entry_config_validity(self) -> bool:
        """Check overall config validity for selected entry using form state."""
        if not self.working_agent.selected_config_component_id:
            return True
        # Create a temporary entry from form state for validation
        temp_entry = ConfigStoreEntryModelView(
            path=self.form_config_path,
            data_type=self.form_config_data_type,
            value=self.form_config_value
        )
        valid, _ = ConfigStoreService.validate_entry_model_view(temp_entry)
        return valid
    
    @rx.var
    def config_validity(self) -> bool:
        """Check if selected config entry is valid using form state."""
        return self.entry_config_validity
    
    def validate_config_entry_from_form_state(self, entry: ConfigStoreEntryModelView) -> tuple[bool, dict[str, bool]]:
        """Validate a config store entry using form state."""
        temp_entry = ConfigStoreEntryModelView(
            path=self.form_config_path,
            data_type=self.form_config_data_type,
            value=self.form_config_value
        )
        valid, errors = ConfigStoreService.validate_entry_model_view(temp_entry)
        
        validity_map = {
            "path": "path" not in errors,
            "json": "value" not in errors or self.form_config_data_type != "JSON",
            "csv": "value" not in errors or self.form_config_data_type != "CSV",
            "config": valid
        }
        
        return valid, validity_map
    
    @rx.var
    def changed_configs_list(self) -> list[str]:
        """Get list of component IDs for changed config entries."""
        return [
            config.component_id
            for config in self.working_agent.config_store
            if config.dict() != config.safe_entry
        ]
    
    @rx.var
    def committed_configs(self) -> list[ConfigStoreEntryModelView]:
        """Get list of committed config store entries."""
        return [
            ConfigStoreEntryModelView(
                path=config.safe_entry.get("path", ""),
                data_type=config.safe_entry.get("data_type", "JSON"),
                value=config.safe_entry.get("value", ""),
                csv_variants=config.csv_variants,
            )
            for config in self.working_agent.config_store
            if not config.uncommitted and config.safe_entry.get("path", "") != ""
        ]
    
    @rx.var
    def has_valid_configs(self) -> bool:
        """Check if agent has valid committed configs."""
        return (
            len(self.working_agent.config_store) > 0 and
            any(not config.uncommitted for config in self.working_agent.config_store)
        )
    
    @rx.var
    def num_of_new_invalid_configs(self) -> int:
        """Count new invalid config entries."""
        return len([
            config for config in self.working_agent.config_store
            if config.uncommitted
        ])
    
    def validate_config_entry(self, entry: ConfigStoreEntryModelView) -> tuple[bool, dict[str, bool]]:
        """Validate a config store entry using ConfigStoreService."""
        valid, errors = ConfigStoreService.validate_entry_model_view(entry)
        
        validity_map = {
            "path": "path" not in errors,
            "json": "value" not in errors or entry.data_type != "JSON",
            "csv": "value" not in errors or entry.data_type != "CSV",
            "config": valid
        }
        
        return valid, validity_map