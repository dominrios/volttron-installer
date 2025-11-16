from typing import Iterable, Literal
import reflex as rx
from loguru import logger
from .model_views import HostEntryModelView, PlatformModelView
from enum import Enum

class ConfigProblemMessages(Enum):
    HOST_CANNOT_BE_RESOLVED = "Host cannot be resolved"
    INSTANCE_NAME_ALREADY_IN_USE = "Instance Name already in use"
    INSTANCE_NAME_INVALID = "Instance Name must contain only letters, numbers, hyphens, and underscores"
    VIP_ADDRESS_MUST_BE_VALID_FORMAT = "Vip Address must be in the format tcp://<ip>:<port>"
    VOLTTRON_HOME_CANNOT_BE_REUSED = "VOLTTRON Homes cannot be the same as another platform under the same host"
    HOST_CONFIGS_DIR_CANNOT_BE_REUSED = "Host config directories cannot be the same as another platform under the same host"

PROBLEM_TAB_MAP = {
    ConfigProblemMessages.HOST_CANNOT_BE_RESOLVED: "connection",
    ConfigProblemMessages.INSTANCE_NAME_ALREADY_IN_USE: "instance_configuration",
    ConfigProblemMessages.INSTANCE_NAME_INVALID: "instance_configuration",
    ConfigProblemMessages.VIP_ADDRESS_MUST_BE_VALID_FORMAT: "instance_configuration",
    ConfigProblemMessages.VOLTTRON_HOME_CANNOT_BE_REUSED: "connection",
    ConfigProblemMessages.HOST_CONFIGS_DIR_CANNOT_BE_REUSED: "connection"
}

class ConfigProblem(rx.Base):
    """Reflex-compatible model for configuration problems."""
    message: str
    tab: str = None
    
    @classmethod
    def create(cls, problem: ConfigProblemMessages) -> "ConfigProblem":
        """Create a ConfigProblem from a ConfigProblemMessages enum."""
        return cls(
            message=problem.value,
            tab=PROBLEM_TAB_MAP[problem]
        )
    
    def matches_enum(self, problem: ConfigProblemMessages) -> bool:
        """Check if this problem matches a given enum."""
        return self.message == problem.value

class Instance(rx.Base):
    # TODO: Implement a system to check the platform,
    # config's uncaught changes as well
    host: HostEntryModelView
    platform: PlatformModelView

    web_bind_address: str = "http://127.0.0.1:8080"
    password: str = ""

    safe_host_entry: dict = {}
    uncaught: bool = False
    valid: bool = False    

    # UI vars
    proxy_config_mode: Literal["None", "HTTP Proxy", "HTTPS Proxy"] = "None"
    web_checked: bool = False
    federation_checked: bool = False
    advanced_expanded: bool = False
    agent_configuration_expanded: bool = False
    selected_tab: Literal["status", "connection", "instance_configuration", "agent_configuration"] = "connection"
    configuration_problems: list[ConfigProblem] = []

    new_instance: bool = True
    deployed: bool = False

    # Business logic methods have been moved to InstanceService
    # Use InstanceService.has_uncaught_changes(self) instead
    # Use InstanceService.does_host_have_errors(self) instead
    # Use InstanceService.refresh_for_copy(self) instead

# Helper functions for configuration problems
def add_configuration_problem(instance: Instance, problem: ConfigProblemMessages) -> None:
    """Add a configuration problem to an instance."""
    problem_obj = ConfigProblem.create(problem)
    
    # Check if already exists
    if not any(p.matches_enum(problem) for p in instance.configuration_problems):
        instance.configuration_problems.append(problem_obj)

def remove_configuration_problem(instance: Instance, problem: ConfigProblemMessages) -> None:
    """Remove a configuration problem from an instance."""
    instance.configuration_problems = [
        p for p in instance.configuration_problems 
        if not p.matches_enum(problem)
    ]

def has_configuration_problem(instance: Instance, problem: ConfigProblemMessages) -> bool:
    """Check if an instance has a specific configuration problem."""
    return any(p.matches_enum(problem) for p in instance.configuration_problems)

def clear_configuration_problems(instance: Instance) -> None:
    """Clear all configuration problems from an instance."""
    instance.configuration_problems = []

def get_problems_for_tab(instance: Instance, tab: str) -> list[ConfigProblem]:
    """Get all configuration problems for a specific tab."""
    return [p for p in instance.configuration_problems if p.tab == tab]

def get_problem_count(instance: Instance) -> int:
    """Get the total number of configuration problems."""
    return len(instance.configuration_problems)

def has_any_problems(instance: Instance) -> bool:
    """Check if an instance has any configuration problems."""
    return len(instance.configuration_problems) > 0

class Tool(rx.Base):
    name: str = ""
    module_path: str = ""
    use_poetry: bool = False

class RequestWhoIsModel(rx.Model):
    device_instance_low: str = ""
    device_instance_high: str = "" 
    dest: str = ""

class ReadDeviceAllModel(rx.Model):
    device_address: str = ""
    device_object_identifier: str = ""

class ScanIPRangeModel(rx.Model):
    network_string: str = ""

class PingIPModel(rx.Model):
    ip_address: str = ""

class ReadPropertyModel(rx.Model):
    device_address: str = ""
    object_identifier: str = ""
    property_identifier: str = ""
    property_array_index: str | int = ""

class WritePropertyModel(rx.Model):
    device_address: str = ""
    object_identifier: str = ""
    property_identifier: str = ""
    value: str = ""
    priority: str | int = ""
    property_array_index: str | int = ""

class WindowsHostIPModel(rx.Base):
    address: str = "" 

class LocalIPModel(rx.Base):
    local_ip: str = ""
    subnet_mask: str = ""
    cidr: str = ""

class NetworkDiscoveryModel(rx.Base):
    status: str = ""
    networks: list[str] = []
    summary: dict = {}
    message: str = ""
    error: str | None = None

class BACnetPointTableFilter(rx.Base):
    volttron_point_name: str = ""
    units: str = ""
    object_type: str = ""
    writable: str = ""
    present_value: str = ""
    index: str = ""
    notes: str = ""

class BACnetPointColumnFilters(rx.Base):
    volttron_point_name: bool = True
    units: bool = True
    object_type: bool = True
    writable: bool = True
    present_value: bool = True
    index: bool = True
    notes: bool = True

class BACnetObjectType(rx.Base):
    value: int
    type_name: str
    writable: bool

class BACnetDevicePointScanStatus(rx.Base):
    object_name: str
    message: str
    device_name: str
    percent_finished: int