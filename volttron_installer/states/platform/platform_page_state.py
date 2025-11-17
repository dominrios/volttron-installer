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


class PlatformPageState(rx.State):
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
        if self.current_uid == "":
            return True
        working_platform: Instance | None = self.platforms.get(self.current_uid, None)
        if working_platform is None:
            return False
        return self.connection_validity(working_platform)[0]
    
    @rx.var
    def host_pinging(self) -> bool:
        return self._host_pinging

    @rx.var
    def is_host_resolvable(self) -> bool:
        return self._host_resolvable


    @rx.var
    def connection_id_validity(self) -> bool:
        if self.current_uid == "":
            return True
        working_platform: Instance | None = self.platforms.get(self.current_uid, None)
        if working_platform is None:
            return False
        return self.connection_validity(working_platform)[1]["id"]
    
    @rx.var
    def connection_ansible_user_validity(self) -> bool:
        if self.current_uid == "":
            return True
        working_platform: Instance | None = self.platforms.get(self.current_uid, None)
        if working_platform is None:
            return False
        return self.connection_validity(working_platform)[1]["ansible_user"]
    
    @rx.var
    def connection_ansible_host_validity(self) -> bool:
        if self.current_uid == "":
            return True
        working_platform: Instance | None = self.platforms.get(self.current_uid, None)
        if working_platform is None:
            return False
        return self.connection_validity(working_platform)[1]["ansible_host"]
    
    @rx.var
    def connection_ansible_port_validity(self) -> bool:
        if self.current_uid == "":
            return True
        working_platform: Instance | None = self.platforms.get(self.current_uid, None)
        if working_platform is None:
            return False
        return self.connection_validity(working_platform)[1]["ansible_port"]

    # ==== vars for platform validation ===
    @rx.var
    def platform_validity(self) -> bool:
        if self.current_uid == "":
            return True
        working_platform: Instance | None = self.platforms.get(self.current_uid, None)
        if working_platform is None:
            return False
        return self.platform_validity(working_platform)[0]
    
    @rx.var
    def platform_instance_name_validity(self)-> bool:
        if self.current_uid == "":
            return True
        working_platform: Instance | None = self.platforms.get(self.current_uid, None)
        if working_platform is None:
            return False
        return self.platform_validity(working_platform)[1]["instance_name"]
    
    @rx.var
    def platform_instance_name_not_in_use(self)-> bool:
        if self.current_uid == "":
            return True
        working_platform: Instance | None = self.platforms.get(self.current_uid, None)
        if working_platform is None:
            return False
        return self.platform_validity(working_platform)[1]["instance_name_not_used"]
    
    @rx.var
    def platform_vip_address_validity(self) -> bool:
        if self.current_uid == "":
            return True
        working_platform: Instance | None = self.platforms.get(self.current_uid, None)
        if working_platform is None:
            return False
        return self.platform_validity(working_platform)[1]["vip_address"]
    # === end of platform validation vars ===

    # === vars for instance validation ===
    @rx.var
    def instance_savable(self) -> bool:
        if self.current_uid == "":
            return False
        working_platform: Instance | None = self.platforms.get(self.current_uid, None)
        if working_platform is None:
            return False
        else:
            return self.check_instance_savable(working_platform)
    
    @rx.var 
    def instance_uncaught(self) -> bool:
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

        yield NavigationState.route_to_platform(new_uid)

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
        working_platform_instance = self.platforms[self.current_uid]
        if field == "id":
            self._host_resolved = False
            setattr(working_platform_instance.host, "ansible_host", value)
        setattr(working_platform_instance.host, field, value)
        working_platform_instance.uncaught = InstanceService.has_uncaught_changes(working_platform_instance)

    @rx.event
    def update_platform_config_detail(self, field: str, value: str):
        working_platform = self.platforms[self.current_uid]
        if field == "web_bind_address":
            setattr(working_platform, field, value)
        else:
            setattr(working_platform.platform.config, field, value)

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
    async def determine_host_reachability(self, working_platform: Instance):
        """On blur of host field, check if the host is reachable"""
        # we have these yield statements scattered because we need make sure when a state var
        # is updated, the app can see it in real time as the function executes. if we dont have it
        # our UI handling the real time spinner will not work as the UI wont be able to read the changed
        # var in real time 
        self._host_pinging = True
        yield
        self._host_resolvable = await self.check_host_reachable(working_platform)
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
        host_id = working_platform.host.id
        if host_id =="":
            return False
        response = await ping_resolvable_host(host_id)
        return response.reachable
        
    def check_instance_uncaught(self, working_platform: Instance) -> bool:
        uncaught: bool = False
        # check if host details are changed
        if working_platform.host.to_dict() != working_platform.safe_host_entry:
            uncaught = True

        # check if platform details are changed but skip the agents field as we will handle that separately
        if {k: v for k, v in working_platform.platform.to_dict().items() if k != 'agents'} != {k: v for k, v in working_platform.platform.safe_platform.items() if k != 'agents'}:
            uncaught = True

        # check if we added some new uncaught agents
        for agent in working_platform.platform.agents.values():
            if agent.is_new:
                logger.debug(f"we found an uncaught agent")
                uncaught = True
                # we can break out of this because we just needed to find at least one brand new uncaught agent
                # to render the platform as uncaught
                break
        
        return uncaught

    def check_instance_savable(self, working_platform: Instance) -> bool:
        savable = True

        # manually check the host and all of its stuff...
        host_dict = working_platform.host.to_dict()
        if (
            host_dict["id"] == "" or \
            host_dict["ansible_user"] == "" or \
            host_dict["ansible_port"].isdigit() == False or \
            host_dict["ansible_host"] == "" or \
            self.is_host_resolvable == False or \
            self.host_pinging or \
            self.host_resolved == False
        ):
            logger.debug("Host is not valid...")
            logger.debug(f"Host ID is empty: {host_dict['id'] == ''}")
            logger.debug(f"Ansible user is empty: {host_dict['ansible_user'] == ''}")
            logger.debug(f"Ansible port is not numeric: {host_dict['ansible_port'].isdigit() == False}")
            logger.debug(f"Ansible host is empty: {host_dict['ansible_host'] == ''}")
            logger.debug(f"Host is not resolvable: {self.is_host_resolvable == False}")
            logger.debug(f"Host is currently pinging: {self.host_pinging}")
            logger.debug(f"Host is not resolved: {self.host_resolved == False}")
            logger.debug(f"Here is the host to prove: {host_dict}")
            savable = False

        # check if platform details are valid 
        platform_valid, platform_valid_map = self.platform_validity(working_platform)
        if platform_valid == False:
            savable = False

        return savable

    def check_instance_deployable(self, working_platform: Instance) -> bool:
        return True if self.check_instance_uncaught(working_platform) == False and working_platform.new_instance == False else False

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