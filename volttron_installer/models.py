import reflex as rx
from loguru import logger
from .model_views import HostEntryModelView, PlatformModelView

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
    web_checked: bool = False
    federation_checked: bool = False
    advanced_expanded: bool = False
    agent_configuration_expanded: bool = False

    new_instance: bool = True
    deployed: bool = False

    # Business logic methods have been moved to InstanceService
    # Use InstanceService.has_uncaught_changes(self) instead
    # Use InstanceService.does_host_have_errors(self) instead
    # Use InstanceService.refresh_for_copy(self) instead

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