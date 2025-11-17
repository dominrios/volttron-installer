"""Platform page state management."""
import reflex as rx
from ...settings import get_settings
from ...model_views import *
from ...utils.create_component_uid import generate_unique_uid
from ...models import *
from ...utils.conversion_methods import json_string_to_csv_string, csv_string_to_usable_dict, identify_string_format, csv_string_to_json_string
from ...utils.validate_content import check_json, check_csv, check_path, check_yaml, check_regular_expression
from ...utils.create_csv_string import create_csv_string, create_and_validate_csv_string
from ...navigation.state import NavigationState
from ...backend.models import AgentType, HostEntry, PlatformConfig, PlatformDefinition, ConfigStoreEntry, AgentDefinition, CreatePlatformRequest, CreateOrUpdateHostEntryRequest, ToolRequest, BACnetDevice, BACnetWritePropertyRequest
from ...utils.prettify import prettify_json
from ...utils import delete_file
from loguru import logger
from typing import Dict, Optional, List
from ...thin_endpoint_wrappers import *
from ...thin_endpoint_wrappers import discover_networks  # Explicit import for the new function
import string, random, json, csv, yaml, re, io, asyncio, math
from copy import deepcopy
from typing import Literal
from bacnet_scan_tool.models import ObjectListNamesResponse
from ...thin_endpoint_wrappers import get_agent_catalog, get_all_platforms, get_hosts
from ...services.instance_service import InstanceService
from ...services.validation_service import ValidationService
from ...states.mixins.form_state_mixin import FormStateMixin


async def __agents_off_catalog__() -> list[AgentModelView]:
    catalog: dict[str, AgentType] = await get_agent_catalog()
    agent_list: list[AgentModelView] = []

    for identity, agent in catalog.items():
        agent_list.append(
            AgentModelView(
                identity=str(identity),
                source=agent.source,
                safe_agent={
                    "identity" : identity,
                    "source" : agent.source,
                    "config" : json.dumps(agent.default_config, indent=4),
                    "config_store" : {
                        path : {
                            "path" : path,
                            "data_type" : config.data_type,
                            "value" : config.value
                        }
                        for path, config in agent.default_config_store.items()
                    }
                },
                config_store_allowed = agent.config_store_allowed,
                config_store=[
                    ConfigStoreEntryModelView(
                        path=path,
                        data_type=entry.data_type,
                        value=str(entry.value),
                        uncommitted=False,
                        is_new=True,
                        safe_entry={
                            "path": path,
                            "data_type": entry.data_type,
                            "value": str(entry.value)
                        }
                    ) for path, entry in agent.default_config_store.items()
                ],
                config=json.dumps(agent.default_config, indent=4),
            )
        )
    return agent_list

async def __instances_from_api__() -> dict[str, Instance]:
    platforms: list[PlatformDefinition] = await get_all_platforms()
    hosts: list[HostEntry] = await get_hosts()
    host_by_id: dict[str, HostEntry] = {}
    for h in hosts:
        # Before we add to the map, lets clear None types for empty strings...
        # alternatively, we could use model_dump() and replace kv pairs with None types
        # to empty strings
        h = HostEntry(**h.to_dict())
        host_by_id[h.id] = h
    
    instances: dict[str, Instance] = {}

    # Creating platform model views, and instances
    for p in platforms:
        working_host_entry = host_by_id[p.host_id]
        host = HostEntryModelView(
            id=p.host_id,
            ansible_user=working_host_entry.ansible_user,
            ansible_host=working_host_entry.ansible_host,
            # For later type validation
            ansible_port=str(working_host_entry.ansible_port),
            http_proxy=working_host_entry.http_proxy,
            https_proxy=working_host_entry.https_proxy,
            volttron_venv=working_host_entry.volttron_venv,
            volttron_home=working_host_entry.volttron_home,
        )

        instance = {
            p.config.instance_name: Instance(
                host=host,
                platform=PlatformModelView(
                    in_file=True,
                    config=PlatformConfigModelView(
                        instance_name=p.config.instance_name,
                        vip_address=p.config.vip_address,
                    ),
                    agents={
                        identity: AgentModelView(
                            identity=identity,
                            source=agent.source,
                            routing_id=identity,
                            safe_agent={
                                "identity" : identity,
                                "source" : agent.source,
                                "config": agent.config,
                            },
                            config_store_allowed=agent.config_store_allowed,
                            config_store=[
                                ConfigStoreEntryModelView(
                                    path=path,
                                    data_type=entry.data_type,
                                    value=str(entry.value),
                                    uncommitted=False,
                                    component_id=generate_unique_uid(),
                                    safe_entry={
                                        "path": path,
                                        "data_type": entry.data_type,
                                        "value": str(entry.value)
                                    },
                                ) for path, entry in agent.config_store.items()
                            ],
                            config="" if agent.config is None else prettify_json(agent.config)[0],
                        )
                        for identity, agent in p.agents.items()
                    }
                ),
                new_instance = False,
                safe_host_entry=host.to_dict(),
            )
        }
        
        instances.update(instance)
    for uid, instance in instances.items():
        instance.platform.safe_platform = instance.platform.to_dict()
        for agent in instance.platform.agents.values():
            for config in agent.config_store:
                # Assign the config's safe_entry
                config.safe_entry = config.dict()
                if config.data_type == "CSV":
                    usable_csv = csv_string_to_usable_dict(config.value)
                    config.csv_variants["Custom"] = usable_csv
            # After going through the agent's config store and assigning the safe entries,
            # we can now assign the agent's safe_agent
            agent.safe_agent = agent.to_dict()

    return instances


class PlatformPageState(rx.State, FormStateMixin):
    #TODO once we save a platform, we create a routing id 
    # off of it's instance name, and redirect the user to 
    # platforms/x, maybe we might have to delete the old 
    # routing id
    session_hydrated: bool = False
    platforms: dict[str, Instance] = {
        # "new": Instance(
        #     host=HostEntryModelView(),
        #     platform=PlatformModelView()
        # )
    }
    _working_platform: Instance = Instance(host=HostEntryModelView(), platform=PlatformModelView())
    list_of_agents: list[AgentModelView] = []

    _host_resolvable: bool = True
    _host_pinging: bool = False
    
    # this var tracks if the host_id that the user is inputting is resolved.
    # as the user inputs a host, we make sure this is false inside of self.update_detail,
    # so we cant save the instance until the host text box has been blurred. once it has, 
    # we can check if the host is reachable or not. if it is, we set this to true.
    _host_resolved: bool = False
    
    # Form state fields (React-like pattern)
    # Host/Connection form fields
    form_ansible_host: str = ""
    form_ansible_user: str = ""
    form_ansible_port: str = ""
    form_http_proxy: str = ""
    form_https_proxy: str = ""
    form_volttron_home: str = ""
    
    # Platform configuration form fields
    form_instance_name: str = ""
    form_vip_address: str = ""
    form_web_bind_address: str = ""
    
    # Form state tracking
    _form_errors: Dict[str, str] = {}
    _form_dirty: Dict[str, bool] = {}
    _form_initialized: bool = False
    _last_initialized_platform_uid: str = ""  # Track which platform we last initialized for
    
    # Field mapping for form-to-model sync
    HOST_FORM_MAPPING = {
        "form_ansible_host": "host.ansible_host",
        "form_ansible_user": "host.ansible_user",
        "form_ansible_port": "host.ansible_port",
        "form_http_proxy": "host.http_proxy",
        "form_https_proxy": "host.https_proxy",
        "form_volttron_home": "host.volttron_home",
    }
    
    PLATFORM_FORM_MAPPING = {
        "form_instance_name": "platform.config.instance_name",
        "form_vip_address": "platform.config.vip_address",
        "form_web_bind_address": "web_bind_address",
    }
    
    @property
    def ALL_FORM_MAPPING(self) -> Dict[str, str]:
        """Combined mapping of all form fields."""
        return {**self.HOST_FORM_MAPPING, **self.PLATFORM_FORM_MAPPING}
    
    # Form error computed vars for React-like access in components
    @rx.var
    def form_error_ansible_user(self) -> str:
        """Get form error for ansible_user field."""
        if not hasattr(self, '_form_errors'):
            return ""
        return self._form_errors.get("form_ansible_user", "")
    
    @rx.var
    def form_error_ansible_port(self) -> str:
        """Get form error for ansible_port field."""
        if not hasattr(self, '_form_errors'):
            return ""
        return self._form_errors.get("form_ansible_port", "")
    
    @rx.var
    def form_error_instance_name(self) -> str:
        """Get form error for instance_name field."""
        if not hasattr(self, '_form_errors'):
            return ""
        return self._form_errors.get("form_instance_name", "")
    
    @rx.var
    def form_error_vip_address(self) -> str:
        """Get form error for vip_address field."""
        if not hasattr(self, '_form_errors'):
            return ""
        return self._form_errors.get("form_vip_address", "")
    
    @rx.var
    def form_error_ansible_host(self) -> str:
        """Get form error for ansible_host field."""
        if not hasattr(self, '_form_errors'):
            return ""
        return self._form_errors.get("form_ansible_host", "")
    
    @rx.var
    def form_error_http_proxy(self) -> str:
        """Get form error for http_proxy field."""
        if not hasattr(self, '_form_errors'):
            return ""
        return self._form_errors.get("form_http_proxy", "")
    
    @rx.var
    def form_error_https_proxy(self) -> str:
        """Get form error for https_proxy field."""
        if not hasattr(self, '_form_errors'):
            return ""
        return self._form_errors.get("form_https_proxy", "")
    
    @rx.var
    def form_error_volttron_home(self) -> str:
        """Get form error for volttron_home field."""
        if not hasattr(self, '_form_errors'):
            return ""
        return self._form_errors.get("form_volttron_home", "")
    
    @rx.var
    def form_error_web_bind_address(self) -> str:
        """Get form error for web_bind_address field."""
        if not hasattr(self, '_form_errors'):
            return ""
        return self._form_errors.get("form_web_bind_address", "")
    
    @rx.var
    def is_hydrated(self) -> bool:
        """Check if state is hydrated."""
        return self.session_hydrated


    # Vars
    @rx.var(cache=True)
    def current_uid(self) -> str:
        return self.router.page.params.get("uid", "")

    @rx.var
    def working_platform(self) -> Instance:
        self._working_platform = self.platforms.get(self.current_uid, Instance(host=HostEntryModelView(), platform=PlatformModelView()))
        return self._working_platform

    @rx.var(cache=True)
    def in_file_platforms(self) -> list[Instance]:
        return [instance for instance in self.platforms.values() if instance.platform.in_file]
    
    @rx.var
    def new_agents_list(self) -> list[str]:
        if self.current_uid == "":
            return []
        working_platform: Instance | None = self.platforms.get(self.current_uid, None)
        if working_platform is None:
            return []
        # logger.debug(f"nah because new agents are : {[agent.identity for agent in working_platform.platform.agents.values() if not agent.is_new]}")
        return [agent.identity for agent in working_platform.platform.agents.values() if not agent.is_new]

    @rx.var
    def platform_title(self) -> str:
        if self.current_uid == "":
            return " "
        working_platform: Instance | None = self.platforms.get(self.current_uid, None)
        if working_platform is None:
            return " "
        else:
            return working_platform.platform.safe_platform['config']['instance_name']

    # === vars for platform details ===
    @rx.var
    def password_field(self) -> str:
        if self.current_uid == "":
            return ""
        working_platform: Instance | None = self.platforms.get(self.current_uid, None)
        if working_platform is None:
            return ""
        return working_platform.password

    @rx.var
    def platform_deployed(self) -> bool:
        if self.current_uid == "":
            return False
        working_platform: Instance | None = self.platforms.get(self.current_uid, None)
        if working_platform is None:
            return ""
        return working_platform.deployed

    # === end of platform detail vars ===

    # ==== vars for connection validation ===
    @rx.var
    def host_resolved(self) -> bool: return self._host_resolved

    @rx.var
    def connection_validity(self) -> bool:
        """Check connection validity using form state."""
        if self.current_uid == "":
            return True
        # Use form-based validation instead of model-based
        return self.form_connection_validity()[0]
    
    @rx.var
    def host_pinging(self) -> bool:
        return self._host_pinging

    @rx.var
    def is_host_resolvable(self) -> bool:
        return self._host_resolvable


    @rx.var
    def connection_id_validity(self) -> bool:
        """Check connection ID validity using form state."""
        if self.current_uid == "":
            return True
        return self.form_connection_validity()[1]["id"]
    
    @rx.var
    def connection_ansible_user_validity(self) -> bool:
        """Check ansible user validity using form state."""
        if self.current_uid == "":
            return True
        return self.form_connection_validity()[1]["ansible_user"]
    
    @rx.var
    def connection_ansible_host_validity(self) -> bool:
        """Check ansible host validity using form state."""
        if self.current_uid == "":
            return True
        return self.form_connection_validity()[1]["ansible_host"]
    
    @rx.var
    def connection_ansible_port_validity(self) -> bool:
        """Check ansible port validity using form state."""
        if self.current_uid == "":
            return True
        return self.form_connection_validity()[1]["ansible_port"]

    # ==== vars for platform validation ===
    @rx.var
    def platform_validity(self) -> bool:
        """Check platform validity using form state."""
        if self.current_uid == "":
            return True
        return self.form_platform_validity()[0]
    
    @rx.var
    def platform_instance_name_validity(self)-> bool:
        """Check instance name validity using form state."""
        if self.current_uid == "":
            return True
        return self.form_platform_validity()[1]["instance_name"]
    
    @rx.var
    def platform_instance_name_not_in_use(self)-> bool:
        """Check if instance name is available using form state."""
        if self.current_uid == "":
            return True
        return self.form_platform_validity()[1]["instance_name_not_used"]
    
    @rx.var
    def platform_vip_address_validity(self) -> bool:
        """Check VIP address validity using form state."""
        if self.current_uid == "":
            return True
        return self.form_platform_validity()[1]["vip_address"]
    # === end of platform validation vars ===

    # === vars for instance validation ===
    @rx.var
    def instance_savable(self) -> bool:
        """Check if instance can be saved using form state."""
        if self.current_uid == "":
            return False
        working_platform: Instance | None = self.platforms.get(self.current_uid, None)
        if working_platform is None:
            return False
        else:
            return self.check_instance_savable(working_platform)
    
    @rx.var 
    def instance_uncaught(self) -> bool:
        """Check if instance has uncaught changes using form dirty state."""
        if self.current_uid == "":
            return False
        working_platform: Instance | None = self.platforms.get(self.current_uid, None)
        if working_platform is None:
            return False
        else:
            return self.check_instance_uncaught(working_platform)
    
    @rx.var
    def instance_deployable(self) -> bool:
        if self.current_uid == "":
            return False
        working_platform: Instance | None = self.platforms.get(self.current_uid, None)
        if working_platform is None:
            return False
        return self.check_instance_deployable(working_platform)
    # === end of instance validation bars ===

    # Events
    @rx.event
    async def hydrate_state(self, force_hydration: bool = False):
        if self.session_hydrated == False or force_hydration:
            # Make sure we have a valid 'blank' agent
            blank_agent = AgentModelView(
                    safe_agent={
                        "identity" : "",
                        "source" : "",
                        "config" : "",
                        "config_store": {}
                    },
                )
            
            self.list_of_agents = await __agents_off_catalog__()
            platforms_from_api = await __instances_from_api__()
            
            # Ensure we have a blank agent that the user can edit as they so choose
            self.list_of_agents.append(
                blank_agent
            )
            self.platforms.update(platforms_from_api)
            self.session_hydrated = True
    
    @rx.event
    def initialize_form_from_model(self):
        """Initialize form state from current working platform."""
        if self.current_uid in self.platforms:
            working_platform = self.working_platform
            # Always re-initialize form from model if:
            # 1. Form was never initialized, OR
            # 2. We're viewing a different platform than last time
            # This ensures form state always reflects the current platform model
            if not self._form_initialized or self._last_initialized_platform_uid != self.current_uid:
                # Call the mixin method to initialize form from model
                FormStateMixin.initialize_form_from_model(self, working_platform, self.ALL_FORM_MAPPING)
                self._last_initialized_platform_uid = self.current_uid
                self._form_initialized = True

    @rx.event(background=True)
    async def delete_temp_uid(self, uid_copy: str):
        import asyncio
        await asyncio.sleep(5)  # Wait for 5 seconds (adjust as needed)
        async with self:
            del self.platforms[uid_copy]
        logger.debug(f"this is the list of param afters: {list(self.platforms.keys())}")

    @rx.event
    def handle_adding_agent(self, agent: AgentModelView, uid: str):
        working_platform = self.platforms[uid]

        # Take a copy of the agent we are adding and make sure we dont have an already existing agent of the same identity
        new_agent: AgentModelView = agent.copy()
        if new_agent.identity in working_platform.platform.agents:
            new_agent.identity = f"{new_agent.identity}_{len(list(working_platform.platform.agents.values()))}"
        
        # Set routing id
        new_agent.routing_id = new_agent.identity if new_agent.identity != "" else generate_unique_uid()

        logger.debug("im going to add new component ids for config store...")
        # go through the config store, create new component ids for each config entry
        for i in new_agent.config_store:
            i.component_id = self.generate_unique_uid()
            logger.debug(f"added component uid: {i.component_id}")

        # Set up the safe agent for validation
        new_agent.safe_agent={
                    "identity": new_agent.identity,
                    "source": new_agent.source,
                    "config": new_agent.config,
                    "config_store" : agent.safe_agent["config_store"]
                }
        logger.debug(f"we added: {new_agent.identity}")
        logger.debug(f" and that safe config store is : {new_agent.safe_agent['config_store']}")
        # Prettify its config and config store contents:
        # loop through our agents one more time, and their config store. make if we 
        # encounter a csv file, then we adjust the "Custom" CSV variant
        for config in new_agent.config_store:
            if config.data_type == "CSV":
                logger.debug(f"this is the config: {config}")
                usable_csv = csv_string_to_usable_dict(config.value)
                config.csv_variants["Custom"] = usable_csv
                logger.debug(f"this is the usable csv: {usable_csv}")
            elif config.data_type == "JSON":
                try:
                    json_data = json.loads(config.value)
                    pretty_json = json.dumps(json_data, indent=4)
                    config.value = pretty_json
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode JSON: {e}")
                    pass

        # if config is json
        logger.debug(f"checking if valid json: {check_json(new_agent.config)}")
        pretty_json, success = prettify_json(new_agent.config)
        if success:
            new_agent.config = pretty_json
        for config in new_agent.config_store:
            # im kind of sick of all of this copy and pasting of block of code:
            # TODO find a better and safer way of doing this 
            working_dict = config.csv_variants[config.selected_variant]
            config.csv_header_row = list(working_dict.keys()) 
            config.formatted_csv = [[working_dict[header] for header in config.csv_header_row] for i in range(10)]
            # ==============================================================
            config.safe_entry = config.dict()
            config.uncommitted = False
        working_platform.platform.agents[new_agent.identity] = new_agent
        yield rx.toast.info(f"{'A new agent' if new_agent.identity == '' else f'Agent {new_agent.identity}'} has been added")
        
    @rx.event
    def handle_removing_agent(self, identity: str):
        working_platform = self.platforms[self.current_uid]
        del(working_platform.platform.agents[identity])
        yield rx.toast.info(f"Agent '{identity}' has been removed")

    @rx.event
    def handle_cancel(self):
        working_platform: Instance = self.platforms[self.current_uid]
        
        # Revert back to our previous host entry
        working_platform.host = HostEntryModelView(**working_platform.safe_host_entry)
        working_platform.uncaught = False
        working_platform.valid = not InstanceService.does_host_have_errors(working_platform)
        
        # Also revert form state if initialized
        if self._form_initialized:
            self.sync_model_to_form(working_platform, self.ALL_FORM_MAPPING)
            # Reset form dirty state after reverting
            for field in self.ALL_FORM_MAPPING.keys():
                self._form_dirty[field] = False

        # Revert back to our previous platform
        working_platform.platform.config.instance_name = working_platform.platform.safe_platform["config"].get("instance_name", "volttron1")
        working_platform.platform.config.vip_address = working_platform.platform.safe_platform["config"].get("vip_address", "tcp://127.0.0.1:22916")
        
        # Revert our platform's agents
        for agent in working_platform.platform.agents.values():
            # We revert the addition of agents that haven't been saved/are default. if the user has 
            # added an agent and has saved the agent previously, we have the agent's safe entry so we 
            # don't need to do anything fancy. Basically if the agent has never been saved before, we can revert
            # the addition of the agent. if it has, we dont do anything about it.
            if agent.is_new:
                del(working_platform.platform.agents[agent.identity])


        logger.debug("i pressed cancel,")
        yield rx.toast.info("Changes Reverted.")

    @rx.event
    async def generate_new_platform(self):
        new_uid = self.generate_unique_uid()
        new_host = HostEntryModelView(id="", ansible_user="", ansible_host="")
        new_platform = PlatformModelView(config=PlatformConfigModelView(), in_file=False)
        new_platform.safe_platform = new_platform.to_dict()
        self.platforms[new_uid] = Instance(
                host=new_host, 
                platform=new_platform,
                safe_host_entry=new_host.to_dict()
            )
        
        # Initialize form state for new platform
        yield NavigationState.route_to_platform(new_uid)
        # Form will be initialized on page load via on_load

    @rx.event
    def copy_platform(self, instance_name: str):
        uid = self.generate_unique_uid()
        copy_instance = deepcopy(self.platforms[instance_name])
        copy_instance.platform.config.instance_name = uid
        InstanceService.refresh_for_copy(copy_instance)
        self.platforms[uid] = copy_instance
        yield NavigationState.route_to_platform(self.platforms[uid].platform.config.instance_name)
        yield rx.toast.info(f"Platform: {instance_name} has been copied")
        # This is a weird way of doing it but we are doing this because 
        # the UI routes to the instance name of a platform. and when we change
        # the instance name after we route to the uid it solves some headaches,
        # but probably should fix the headaches that it would cause.
        copy_instance.platform.config.instance_name = instance_name
        # yield self.update_platform_config_detail("instance_name", instance_name)
        
    @rx.event
    def toggle_advanced(self):
        working_platform: Instance = self.platforms[self.current_uid]
        working_platform.advanced_expanded = not working_platform.advanced_expanded
    
    @rx.event
    def toggle_agent_config_details(self):
        working_platform: Instance = self.platforms[self.current_uid]
        working_platform.agent_configuration_expanded = not working_platform.agent_configuration_expanded

    @rx.event
    def toggle_web(self):
        working_platform: Instance = self.platforms[self.current_uid]
        working_platform.web_checked = not working_platform.web_checked

    @rx.event
    def toggle_federation(self):
        working_platform: Instance = self.platforms[self.current_uid]
        working_platform.federation_checked = not working_platform.federation_checked

    @rx.event
    def update_password_field(self, value: str):
        working_platform_instance = self.platforms[self.current_uid]
        working_platform_instance.password = value

    @rx.event
    def update_detail(self, field: str, value):
        """Update host detail - supports both model-based and form-based updates."""
        working_platform_instance = self.platforms[self.current_uid]
        if field == "id":
            self._host_resolved = False
            setattr(working_platform_instance.host, "ansible_host", value)
            # Also update form state if using forms
            if hasattr(self, 'form_ansible_host'):
                self.form_ansible_host = value
        else:
            setattr(working_platform_instance.host, field, value)
            # Also update form state if using forms
            form_field = f"form_{field}"
            if hasattr(self, form_field):
                setattr(self, form_field, value)
        
        working_platform_instance.uncaught = InstanceService.has_uncaught_changes(working_platform_instance)
    
    @rx.event
    def update_form_host_field(self, field: str, value: str):
        """Update host form field with validation."""
        # Map field names
        field_mapping = {
            "ansible_host": "form_ansible_host",
            "ansible_user": "form_ansible_user",
            "ansible_port": "form_ansible_port",
            "http_proxy": "form_http_proxy",
            "https_proxy": "form_https_proxy",
            "volttron_home": "form_volttron_home",
        }
        
        form_field = field_mapping.get(field, f"form_{field}")
        
        # Get appropriate validator
        validators = {
            "ansible_host": lambda v: ValidationService.validate_host(v),
            "ansible_user": lambda v: ValidationService.validate_required(v, "Username"),
            "ansible_port": lambda v: ValidationService.validate_port(v),
            "http_proxy": lambda v: (True, ""),  # Optional field, no validation needed
            "https_proxy": lambda v: (True, ""),  # Optional field, no validation needed
            "volttron_home": lambda v: (True, ""),  # Optional field, no validation needed
        }
        
        validator = validators.get(field)
        self.update_form_field(form_field, value, validator)
        
        # Sync form to model immediately to preserve changes across navigation
        # This ensures unsaved form data is preserved in the model
        if self.session_hydrated and self.current_uid in self.platforms:
            working_platform = self.platforms[self.current_uid]
            self.sync_form_to_model(working_platform, self.ALL_FORM_MAPPING)
        
        # Reset host resolved state when host changes (for reachability check)
        if field == "ansible_host":
            self._host_resolved = False

    @rx.event
    def update_platform_config_detail(self, field: str, value: str):
        """Update platform config detail - supports both model-based and form-based updates."""
        working_platform = self.platforms[self.current_uid]
        if field == "web_bind_address":
            setattr(working_platform, field, value)
            # Also update form state if using forms
            if hasattr(self, 'form_web_bind_address'):
                self.form_web_bind_address = value
        else:
            setattr(working_platform.platform.config, field, value)
            # Also update form state if using forms
            form_field = f"form_{field}"
            if hasattr(self, form_field):
                setattr(self, form_field, value)
    
    @rx.event
    def update_form_platform_field(self, field: str, value: str):
        """Update platform form field with validation."""
        # Map field names
        field_mapping = {
            "instance_name": "form_instance_name",
            "vip_address": "form_vip_address",
            "web_bind_address": "form_web_bind_address",
        }
        
        form_field = field_mapping.get(field, f"form_{field}")
        
        # Get appropriate validator
        validators = {
            "instance_name": lambda v: ValidationService.validate_instance_name(v),
            "vip_address": lambda v: ValidationService.validate_vip_address(v),
            "web_bind_address": lambda v: (True, ""),  # Optional field, basic URL validation could be added
        }
        
        validator = validators.get(field)
        self.update_form_field(form_field, value, validator)
        
        # Sync form to model immediately to preserve changes across navigation
        # This ensures unsaved form data is preserved in the model
        if self.session_hydrated and self.current_uid in self.platforms:
            working_platform = self.platforms[self.current_uid]
            self.sync_form_to_model(working_platform, self.ALL_FORM_MAPPING)

    @rx.event
    async def handle_deploy(self):
        working_platform: Instance = self.platforms[self.current_uid]
        try:
            response = await deploy_platform(working_platform.platform.config.instance_name, working_platform.password)
            working_platform.deployed = True
            logger.debug(f"response: {response.json()}")
            yield rx.toast.success("Deployed Successfully!")
        except Exception as e:
            logger.debug(f"there was an error deploying platform {working_platform.platform.config.instance_name}. e: {e}")
            yield rx.toast.error(f"There was an error deploying platform: {working_platform.platform.config.instance_name}")

    @rx.event
    async def handle_save(self):
        working_platform: Instance = self.platforms[self.current_uid]
        uid_copy = deepcopy(self.current_uid)

        logger.debug(f"this is the uid copy: {uid_copy}")
        all_platforms: list[PlatformDefinition] = await get_all_platforms()
        
        # Sync form state to model before saving
        if self._form_initialized:
            self.sync_form_to_model(working_platform, self.ALL_FORM_MAPPING)
            # Reset form dirty state after sync
            for field in self.ALL_FORM_MAPPING.keys():
                self._form_dirty[field] = False

        working_platform.safe_host_entry = working_platform.host.to_dict()
        working_platform.uncaught = False
        
        # TODO save the federation field once we have it all up and running
        # federation = working_platform.enable_federation

        # Create base platform
        base_platform_request = CreatePlatformRequest(
            host_id = working_platform.safe_host_entry["id"],
            config=PlatformConfig(
                instance_name=working_platform.platform.config.instance_name,
                vip_address=working_platform.platform.config.vip_address
            ),
            agents = {
                identity: AgentDefinition(
                    identity=identity,
                    source=agent["source"],
                    config=agent["config"],
                    config_store_allowed=agent["config_store_allowed"],
                    config_store={
                        path: ConfigStoreEntry(
                            path=path,
                            data_type=config["data_type"],
                            value=config["value"]
                        ) for path, config in agent["config_store"].items()
                    }
                ) for identity, agent in working_platform.platform.to_dict()["agents"].items()
            }
        )

        logger.debug(f"this is the uid copy: {uid_copy}")
        if working_platform.platform.config.instance_name in [p.config.instance_name for p in all_platforms]:
            logger.debug("yes we have committed this already")
            await update_platform(
                working_platform.platform.config.instance_name,
                base_platform_request
            )
            yield rx.toast.success("Changes saved successfully")
            return
        
        host_request = working_platform.host.to_dict()
        host_request["ansible_port"] = int(host_request["ansible_port"])
        host_request["name"] =  working_platform.platform.config.instance_name
        request = CreateOrUpdateHostEntryRequest(**host_request)

        await add_host(request)
        await create_platform(base_platform_request)
        
        # Lets say changes saved successfully and redirect to the new url while deleting our old one
        logger.debug(f"this is the uid copy: {uid_copy}")
        yield rx.toast.success("Changes saved successfully")
        self.platforms[working_platform.platform.config.instance_name] = working_platform
        logger.debug(f"this is the list of params: {list(self.platforms.keys())}")
        yield NavigationState.route_to_platform(working_platform.platform.config.instance_name)
        logger.debug(f"this is the uid about to deletee: {uid_copy}")
        yield PlatformPageState.delete_temp_uid(uid_copy)
        yield PlatformPageState.hydrate_state(True)

    @rx.event
    async def determine_host_reachability(self):
        """On blur of host field, check if the host is reachable - uses form state"""
        # we have these yield statements scattered because we need make sure when a state var
        # is updated, the app can see it in real time as the function executes. if we dont have it
        # our UI handling the real time spinner will not work as the UI wont be able to read the changed
        # var in real time 
        self._host_pinging = True
        yield
        # Use form state instead of model
        self._host_resolvable = await self.check_host_reachable_from_form()
        self._host_pinging = False
        yield
        self._host_resolved = self._host_resolvable
        yield
        return

    @rx.event
    def cement_registry_config(self, working_platform: Instance):
        logger.debug("Cementing registry config...")
        self.platforms[working_platform.platform.config.instance_name] = working_platform


    # NOTE: i would like to offload the uncaught and valid vars into the state vars because it's easier for the UI to read off of 
    # state vars, for faster development, ive kept these here and i'll change it once it's time to refine the code.
    #   Secondary NOTE: not sure if i've already made changes.
    def handle_uncaught(self, working_platform: Instance):
        working_platform.uncaught = InstanceService.has_uncaught_changes(working_platform)

    def handle_validity(self, working_platform: Instance):
        working_platform.valid = not InstanceService.does_host_have_errors(working_platform)

    def generate_unique_uid(self, length=7) -> str:
        characters = string.ascii_letters + string.digits
        while True:
            new_uid = ''.join(random.choice(characters) for _ in range(length))
            if new_uid not in self.platforms:
                return new_uid
    
    # functions to check if things are savable, reachable, valid, uncaught.
    async def check_host_reachable(self, working_platform: Instance) -> bool:
        """Check host reachability from model (legacy method)."""
        host_id = working_platform.host.id
        if host_id =="":
            return False
        response = await ping_resolvable_host(host_id)
        return response.reachable
    
    async def check_host_reachable_from_form(self) -> bool:
        """Check host reachability from form state."""
        host_id = self.form_ansible_host
        if host_id == "":
            return False
        response = await ping_resolvable_host(host_id)
        return response.reachable
        
    def check_instance_uncaught(self, working_platform: Instance = None) -> bool:
        """Check if instance has uncaught changes - uses form dirty state and agents."""
        uncaught: bool = False
        
        # Check if form has any dirty fields (form-based approach)
        if self.is_form_dirty():
            uncaught = True
            logger.debug("Form has dirty fields")
        
        # Also check if we added some new uncaught agents (this still needs model)
        # TODO: Consider moving agent state to form state in future
        if working_platform is not None:
            for agent in working_platform.platform.agents.values():
                if agent.is_new:
                    logger.debug(f"we found an uncaught agent")
                    uncaught = True
                    # we can break out of this because we just needed to find at least one brand new uncaught agent
                    # to render the platform as uncaught
                    break
        
        return uncaught

    def check_instance_savable(self, working_platform: Instance = None) -> bool:
        """Check if instance can be saved - uses form state instead of model."""
        savable = True

        # Check form validation errors first
        if not self.is_form_valid():
            logger.debug("Form has validation errors")
            savable = False

        # Check form fields directly (using form state)
        if (
            self.form_ansible_host == "" or
            self.form_ansible_user == "" or
            self.form_ansible_port == "" or
            not self.form_ansible_port.isdigit() or
            self.is_host_resolvable == False or
            self.host_pinging or
            self.host_resolved == False
        ):
            logger.debug("Host form fields are not valid...")
            logger.debug(f"Host ID is empty: {self.form_ansible_host == ''}")
            logger.debug(f"Ansible user is empty: {self.form_ansible_user == ''}")
            logger.debug(f"Ansible port is not numeric: {not self.form_ansible_port.isdigit()}")
            logger.debug(f"Host is not resolvable: {self.is_host_resolvable == False}")
            logger.debug(f"Host is currently pinging: {self.host_pinging}")
            logger.debug(f"Host is not resolved: {self.host_resolved == False}")
            savable = False

        # Check if platform details are valid using form state
        platform_valid, platform_valid_map = self.form_platform_validity()
        if platform_valid == False:
            logger.debug("Platform form fields are not valid")
            savable = False

        return savable

    def check_instance_deployable(self, working_platform: Instance) -> bool:
        return True if self.check_instance_uncaught(working_platform) == False and working_platform.new_instance == False else False

    # Form-based validation methods (read from form state, not model)
    def form_connection_validity(self) -> tuple[bool, dict[str, bool]]:
        """Validate connection using form state instead of model."""
        valid = True
        validity_map: dict[str, bool] = {
            "id": True,
            "ansible_user": True,
            "ansible_host": True,
            "ansible_port": True,
            "http_proxy": True,
            "https_proxy": True,
            "volttron_venv": True,
            "volttron_home": True
        }
        
        # Validate the host id (from form_ansible_host)
        if self.form_ansible_host == "":
            valid = False
            validity_map["id"] = False
        
        # Validate the ansible user
        if self.form_ansible_user == "":
            valid = False
            validity_map["ansible_user"] = False
        
        # Validate the ansible host
        if self.form_ansible_host == "":
            valid = False
            validity_map["ansible_host"] = False
        
        # Validate the ansible port
        if self.form_ansible_port == "" or not self.form_ansible_port.isnumeric():
            valid = False
            validity_map["ansible_port"] = False
        
        return (valid, validity_map)
    
    def form_platform_validity(self) -> tuple[bool, dict[str, bool]]:
        """Validate platform using form state instead of model."""
        valid = True
        validity_map: dict[str, bool] = {
            "instance_name": True,
            "instance_name_not_used": True,
            "vip_address": True
        }
        
        # Validate the instance name
        valid_field_name_for_instance = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-/-]*$")
        if not valid_field_name_for_instance.fullmatch(self.form_instance_name):
            valid = False
            validity_map["instance_name"] = False
        
        # Check to see if our instance name is taken already
        existing_names = [
            p.platform.safe_platform["config"]["instance_name"] 
            for p in self.in_file_platforms 
            if p.new_instance == False and self.current_uid != p.platform.safe_platform["config"]["instance_name"]
        ]
        
        if self.form_instance_name in existing_names:
            valid = False
            validity_map["instance_name_not_used"] = False
        
        # Validate the tcp address
        if not re.match(r'^tcp://[\d.]+:\d+$', self.form_vip_address):
            valid = False
            validity_map["vip_address"] = False
        
        return (valid, validity_map)

    def connection_validity(self, working_platform: Instance) -> tuple[bool, dict[str, bool]]:
        valid = True
        validity_map: dict[str, bool] = {
            "id" : True,
            "ansible_user" : True,
            "ansible_host" : True,
            "ansible_port" : True,
            "http_proxy" : True,
            "https_proxy" : True,
            "volttron_venv" : True,
            "volttron_home" : True
        }
        # Validate the host id
        if working_platform.host.id == "":
            valid = False
            validity_map["id"] = False

        # Validate the ansible user
        if working_platform.host.ansible_user == "":
            valid = False
            validity_map["ansible_user"] = False

        # Validate the ansible host
        if working_platform.host.ansible_host == "":
            valid = False
            validity_map["ansible_host"] = False

        # Validate the ansible port
        if not isinstance(working_platform.host.ansible_port, int):
            if not working_platform.host.ansible_port.isnumeric():
                valid = False
                validity_map["ansible_port"] = False

        return (valid, validity_map)

    def platform_validity(self, working_platform: Instance) -> tuple[bool, dict[str, bool]]:
        valid = True
        validity_map: dict[str, bool] = {
            "instance_name" : True,
            "instance_name_not_used" : True,
            "vip_address" : True
        }
        # Validate the instance name
        valid_field_name_for_instance = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-/-]*$")
        if not valid_field_name_for_instance.fullmatch(working_platform.platform.config.instance_name):
            valid = False
            validity_map["instance_name"] = False
        
        new_name = working_platform.platform.config.instance_name
        existing_names=[p.platform.safe_platform["config"]["instance_name"] for p in self.in_file_platforms if p.new_instance == False and self.current_uid != p.platform.safe_platform["config"]["instance_name"]]

        # Check to see if our instance is taken already:
        # Seeing if our instance name is inside a list of already registered instance names...
        if working_platform.platform.config.instance_name in [p.platform.safe_platform["config"]["instance_name"] for p in self.in_file_platforms if p.new_instance == False and self.current_uid != p.platform.safe_platform["config"]["instance_name"]]:
            valid = False
            validity_map["instance_name_not_used"] = False
            

        # Validate the tcp address
        if not re.match(r'^tcp://[\d.]+:\d+$', working_platform.platform.config.vip_address):
            valid = False
            validity_map["vip_address"] = False

        return (valid, validity_map)