import reflex as rx
from volttron_installer.model_views import AgentModelView
from ..layouts.app_layout import app_layout
from ..components.tiles import config_tile
from ..components.ui.buttons import icon_button_wrapper
from ..components.header.header import header
from ..components.ui.buttons.tile_icon import tile_icon
from ..navigation.state import NavigationState
from ..components.form_components import form_entry
from typing import Literal
from ..thin_endpoint_wrappers import *
from ..state import PlatformPageState as State
from ..models import Instance

parts = Literal["connection", "instance_configuration"]

def status_tab() -> rx.Component:
    return rx.vstack(
        rx.grid( # Quick status checks
            status_tile(
                heading="Platform Status",
                content="Online",
                supplementary_text="Uptime: 12d 4h 32m"
            ),
            status_tile(
                heading="Total Agents",
                content="8",
                supplementary_text="Installed Agents"
            ),
            status_tile(
                heading="Active Agents",
                content="6",
                supplementary_text="Currently Running"
            ),
            status_tile(
                heading="Health Status",
                content="6/8",
                supplementary_text="Healthy Agents"
            ),
            width="100%",
            spacing="6",
            columns={ "base": "1", "md": "4" },
        ),
        rx.box( # Agent table card
            rx.box(  # CardHeader
                rx.text("Agent Management", size="5", weight="bold"),
                rx.text("Monitor and control your VOLTTRON agents", size="1", color="gray")
            ),
            rx.box( # Card Content
                rx.box(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Agent Name"),
                                rx.table.column_header_cell("Status"),
                                rx.table.column_header_cell("State"),
                                rx.table.column_header_cell("Version"),
                                rx.table.column_header_cell("Last Seen"),
                                rx.table.column_header_cell("Actions"),
                            )
                        ),
                        rx.table.body(
                            rx.foreach(
                                State.working_platform.platform.agents,
                                lambda identity_agent_pair: render_agent_row(identity_agent_pair[1])
                            ),
                        )
                    )
                )
            ),
            border="1px solid",
            border_color="grey",
            border_radius=".5rem",
            box_shadow="0 4px 12px rgba(0,0,0,0.08)",
            padding="1.3rem",
        ),
        align_items="stretch",
        spacing="6"
    )

def connection_tab() -> rx.Component:
    return rx.box(
        rx.box(  # CardHeader
            rx.hstack(
                rx.text("Connection Configuration", size="5", weight="bold"),
                spacing="2",
                align="center"
            ),
            rx.text("Configure your VOLTTRON platform connection settings", size="2", color="gray"),
            margin_bottom="0.8rem"
        ),
        rx.vstack(  # CardContent
            rx.grid(
                rx.vstack(
                    rx.hstack(
                        rx.text("Host ", rx.text.span("*", color="red"), as_="label", html_for="host"),
                        rx.cond(
                            State.host_pinging,
                            rx.spinner(),
                            rx.cond(
                                State.is_host_resolvable,
                                tile_icon(
                                    "check"
                                ),
                                tile_icon(
                                    "triangle-alert"
                                )
                            )
                        ),
                        width="100%",
                        justify="between",
                        align="center",
                    ),
                    rx.input(
                        id="host",
                        placeholder="localhost",
                        width="100%",
                        value= State.working_platform.host.ansible_host,
                        on_change=lambda v: State.update_detail("id", v),
                        on_blur=lambda: State.determine_host_reachability(State.working_platform),
                    ),
                    rx.cond(
                        State.is_host_resolvable == False,
                        rx.text(
                            "Host must be a valid domain or ip address",
                            size="1",
                            color_scheme="red",
                        )
                    ),
                    width="100%",
                    spacing="2",
                    align="start",
                ),
                rx.vstack(
                    rx.text("Username ", rx.text.span("*", color="red"), as_="label", html_for="username"),
                    rx.input(
                        id="username",
                        placeholder="volttron",
                        width="100%",
                        value=State.working_platform.host.ansible_user,
                        on_change=lambda v: State.update_detail("ansible_user", v),
                    ),
                    rx.text(
                        "Username must have SUDO permissions",
                        size="1",
                        color_scheme="gray"
                    ),
                    width="100%",
                    spacing="2",
                    align="start",
                ),
                width="100%",
                columns={ "base": "1", "md": "2" },
                spacing="3"
            ),
            rx.grid(
                rx.vstack(
                    rx.vstack(
                        rx.text("Port SSH ", rx.text.span("*", color="red"), as_="label", html_for="port_ssh"),
                        rx.input(
                            id="port_ssh",
                            placeholder="22",
                            width="100%",
                            value=State.working_platform.host.ansible_port,
                            on_change=lambda v: State.update_detail("ansible_port", v),
                        ),
                        rx.cond(
                            State.connection_ansible_port_validity == False,
                            rx.text(
                                "Port SSH must be a valid port number",
                                size="1",
                                color_scheme="red"
                            )
                        ),
                        width="100%",
                        spacing="2",
                        align="start",
                    )
                ),
                width="100%",
                columns="1",
            ),
            rx.divider(),
            rx.hstack(
                rx.switch(
                    checked=State.working_platform.advanced_expanded,
                    on_change=lambda: State.toggle_advanced(State.current_uid)
                ), 
                rx.text("Toggle Advanced Settings"), 
                spacing="2"
            ),
            rx.divider(),
            # Advanced Settings...
            rx.cond(
                State.working_platform.advanced_expanded,
                rx.fragment(
                    rx.grid(
                        rx.text("Proxy Configuration", as_="label", html_for="proxy-config"),
                        rx.vstack(
                            rx.radio_group(
                                [
                                    "None",
                                    "HTTP Proxy",
                                    "HTTPS Proxy",
                                ],
                                id="proxy-config",
                                direction="column",
                                on_change=State.set_proxy_config_mode,
                                value=State.working_platform.proxy_config_mode,
                            ),
                            padding="0.5rem",
                        ),
                        rx.cond(
                            State.working_platform.proxy_config_mode != "None",
                            rx.input(
                                width="100%", 
                                placeholder=rx.cond(
                                    State.working_platform.proxy_config_mode == "HTTP Proxy",
                                    "Enter HTTP Proxy URL",
                                    "Enter HTTPS Proxy URL"
                                ),
                                on_change=lambda v: State.update_detail(
                                    rx.cond(
                                        State.working_platform.proxy_config_mode == "HTTP Proxy",
                                        "http_proxy",
                                        "https_proxy"
                                    ),
                                    v
                                ),
                                value=rx.cond(
                                    State.working_platform.proxy_config_mode == "HTTP Proxy",
                                    State.working_platform.host.http_proxy,
                                    State.working_platform.host.https_proxy
                                )
                            )
                        ),
                        columns="1",
                        width="100%"
                    ),
                    # TODO: Pull in the checks for volttron home and host configs dir
                    rx.grid(
                        rx.vstack(
                            rx.text("VOLTTRON Home", as_="label", html_for="volttron-home"),
                            rx.input(
                                id="volttron-home",
                                placeholder="~/.volttron",
                                width="100%",
                                # value=BacnetScanState.proxy_field_value,
                                # on_change=BacnetScanState.handle_proxy_field_edit,
                            ),
                            rx.text(
                                "VOLTTRON Homes cannot be the same as another platform under the same host.",
                                size="1",
                                color_scheme="red",
                            ),
                            width="100%",
                            spacing="2",
                            align="start",
                        ),
                        rx.vstack(
                            rx.text("Host Configs Directory", as_="label", html_for="host-configs-dir"),
                            rx.input(
                                id="host-configs-dir",
                                placeholder="~/.volttron",
                                width="100%",
                                # value=BacnetScanState.proxy_field_value,
                                # on_change=BacnetScanState.handle_proxy_field_edit,
                            ),
                            rx.text(
                                "Host Config Directories cannot be the same as another platform under the same host.",
                                size="1",
                                color_scheme="red",
                            ),
                            width="100%",
                            spacing="2",
                            align="start",
                        ),
                        width="100%",
                        columns={ "base": "1", "md": "2" },
                        spacing="3"
                    ),
                    rx.divider()
                )
            ),
            spacing="4",
            margin_bottom="1rem"
        ),
        rx.hstack( # CardFooter
            rx.button(
                "Next: Instance Configuration",
                on_click=lambda: State.set_platform_tab("instance_configuration")
            ),
            justify="end",
        ),
        border="1px solid",
        border_color="grey",
        border_radius=".5rem",
        box_shadow="0 4px 12px rgba(0,0,0,0.08)",
        padding="1.3rem",
    )

def instance_configuration_tab() -> rx.Component:
    return rx.box(
        rx.box(  # CardHeader
            rx.hstack(
                rx.text("Instance Configuration", size="5", weight="bold"),
                spacing="2",
                align="center"
            ),
            rx.text("Configure your VOLTTRON platform instance settings", size="2", color="gray"),
            margin_bottom="0.8rem"
        ),
        rx.vstack(  # CardContent
            rx.grid(
                rx.vstack(
                    rx.text("Instance Name ", rx.text.span("*", color="red"), as_="label", html_for="instance-name"),
                    rx.input(
                        id="instance-name",
                        placeholder="volttron1",
                        width="100%",
                        value=State.working_platform.platform.config.instance_name,
                        on_change=lambda v: State.update_platform_config_detail("instance_name", v),
                    ),
                    # TODO add conditional to turn text red if error
                    rx.text(
                        "Instance Name must contain only letters, numbers, hyphens, and underscores",
                        size = "1",
                        color_scheme = rx.cond(
                            State.platform_instance_name_validity == False,
                            "red",
                            "gray"
                        )
                    ),
                    rx.cond(
                        State.platform_instance_name_not_in_use == False,
                        rx.text(
                            "Instance Name already in use", 
                            color_scheme = "red",
                            size = "1"
                        )
                    ),
                    width="100%",
                    spacing="2",
                    align="start",
                ),
                rx.vstack(
                    rx.text("Vip Address ", rx.text.span("*", color="red"), as_="label", html_for="vip-address"),
                    rx.input(
                        id="vip-address",
                        placeholder="tcp://127.0.0.1:22916",
                        width="100%",
                        value=State.working_platform.platform.config.vip_address,
                        on_change=lambda v: State.update_platform_config_detail("vip_address", v),
                    ),
                    rx.text(
                        "Vip Address must be in the format tcp://<ip>:<port>", 
                        size="1",
                        color_scheme=rx.cond(
                            State.platform_vip_address_validity == False,
                            "red",
                            "gray"
                        )
                    ),
                    width="100%",
                    spacing="2",
                    align="start",
                ),
                width="100%",
                columns={ "base": "1", "md": "2" },
                spacing="3"
            ),
            rx.grid(
                rx.vstack(
                    #TODO add conditional for web address if checked 
                    rx.vstack(
                        rx.hstack(
                            rx.checkbox(
                                id="member-of-federation",
                                on_click = lambda: State.toggle_federation(),
                                checked=State.working_platform.federation_checked
                            ),
                            rx.text("Member of Federation", as_="label", html_for="member-of-federation"),
                            spacing="2",
                            align="start",
                        ),
                        rx.hstack(
                            rx.checkbox(
                                id="web",
                                checked=State.working_platform.web_checked,
                                on_change=lambda: State.toggle_web()
                            ),
                            rx.text("Web", as_="label", html_for="web"),
                            spacing="2",
                            align="start",
                        ),
                        # This is the leaf component that appears under the checkbox with a vertical line
                        rx.cond(
                            State.working_platform.web_checked,
                            rx.hstack(
                                # Vertical line on the left
                                rx.box(
                                    width="2px",
                                    background_color="#272727FF",
                                    height="100%",
                                    margin_left="6px",  # Margin left to align with checkbox
                                ),
                                # Field content
                                rx.vstack(
                                    rx.text("Web Bind Address", as_="label", html_for="web-bind-address"),
                                    rx.input(
                                        id="web-bind-address",
                                        placeholder="",
                                        value=State.working_platform.web_bind_address,
                                        on_change=lambda v: State.update_platform_config_detail("web_bind_address", v),
                                    ),
                                    align="start",
                                    spacing="1",
                                    width="100%",
                                    padding_left="6px",  # Padding left to create space from the vertical line
                                ),
                                align_items="flex-start",
                                width="100%",
                            )
                        ),
                        align_items="flex-start",
                        width="100%",
                        spacing="0",  # Reduce space between checkbox and leaf
                    )
                ),
                width="100%",
                columns="1",
            ),
            rx.divider(),
            spacing="4",
            margin_bottom="1rem"
        ),
        rx.hstack( # CardFooter
            rx.button(
                "Back: Connection",
                on_click=lambda: State.set_platform_tab("connection", State.working_platform),
                variant="outline"
            ),
            rx.button(
                "Next: Agent Configuration",
                on_click=lambda: State.set_platform_tab("agent_configuration", State.working_platform)
            ),
            justify="between",
        ),
        border="1px solid",
        border_color="grey",
        border_radius=".5rem",
        box_shadow="0 4px 12px rgba(0,0,0,0.08)",
        padding="1.3rem",
    )

def agent_configuration_tab() -> rx.Component:
    return rx.vstack(
        rx.grid(
            rx.box( # Listed Agents Card
                rx.box(  # CardHeader
                    rx.hstack(
                        rx.text("Listed Agents", size="5", weight="bold"),
                        spacing="2",
                        align="center"
                    ),
                    rx.text("Select agents to add to your platform", size="2", color="gray"),
                    margin_bottom="0.8rem"
                ),
                rx.box( # Card Content - Changed from vstack to box with position
                    rx.vstack( # Content wrapper
                        rx.foreach(
                            State.list_of_agents,
                            lambda agent: add_agent_tile(
                                agent=agent
                            )
                        ),
                        width="100%",
                    ),
                    overflow_y="auto",
                    height="35rem",
                    width="100%",
                    padding_right=".75rem",
                    position="relative", # Added position
                ),
                border="1px solid",
                border_color="grey",
                border_radius=".5rem",
                box_shadow="0 4px 12px rgba(0,0,0,0.08)",
                padding="1.3rem",
                display="flex", # Added display flex
                flex_direction="column", # Ensure vertical layout
            ),
            rx.box(
                rx.box( # Card Header
                    rx.hstack(
                        rx.text("Added Agents", size="5", weight="bold"),
                        spacing="2",
                        align="center"
                    ),
                    rx.text("Configure, update, or remove added agents on your platform", size="2", color="gray"),
                    margin_bottom="0.8rem"
                ),
                rx.box(  # Card Content
                    rx.vstack( # Content wrapper
                        rx.foreach(
                            State.working_platform.platform.agents,
                            lambda identity_agent_pair: added_agent_tile(
                                agent=identity_agent_pair[1]
                            )
                        ),
                        width="100%",
                    ),
                    overflow_y="auto",
                    height="35rem",
                    width="100%",
                    padding_right=".75rem",
                    position="relative", # Added position
                ),
                border="1px solid",
                border_color="grey",
                border_radius=".5rem",
                box_shadow="0 4px 12px rgba(0,0,0,0.08)",
                padding="1.3rem",
                display="flex", # Added display flex
                flex_direction="column", # Ensure vertical layout
            ),
            spacing="2",
            columns={ "base" : "1", "md" : "2" },
            width="100%",
        ),
        rx.hstack(
            rx.button(
                "Back: Instance Configuration",
                on_click=lambda: State.set_platform_tab("instance_configuration"),
                variant="outline"
            ),
            rx.vstack(
                rx.dialog.root(
                rx.dialog.trigger(
                    rx.button(
                        rx.cond(
                            State.platform_deployed,
                            "Save and Re-Deploy",
                            "Save and Deploy"
                        ),
                        color_scheme = "green",
                        disabled = rx.cond(
                            State.instance_savable,
                            # (State.instance_savable)
                            # & (State.instance_uncaught),
                            False,
                            True
                        )
                    ),
                ),
                rx.dialog.content(
                    rx.dialog.title("Password Required"),
                    rx.dialog.description("To deploy, please provide your ssh password"),
                    rx.vstack(
                        rx.vstack(
                            form_entry.form_entry(
                                "Password",
                                rx.input(
                                    type="password",
                                    on_change=State.update_password_field,
                                    value=State.password_field
                                ),
                                required_entry=True
                            ),
                            align="center",
                            justify="center"
                        ),
                        rx.hstack(
                            rx.dialog.close(
                                rx.button(
                                    "Cancel",
                                    variant="soft",
                                    color_scheme="gray",
                                )
                            ),
                            rx.dialog.close(
                                rx.button(
                                    "Submit",
                                    on_click=lambda: State.handle_save_deploy(),
                                    disabled=rx.cond(
                                        State.password_field=="",
                                        True,
                                        False
                                    )
                                )
                            ),
                            spacing="3",
                            justify="end",
                        ),
                        width="100%",
                        padding_top="1rem",
                        spacing="6"
                    )
                )
                ),
                rx.cond(
                    ~State.instance_savable,
                    configuration_problem_tooltip()
                )
            ),
            justify="between",
            width="100%",
        ),
        spacing="4",
        width="100%",
    )

@rx.memo
def status_tile(heading: str, content: str, supplementary_text: str) -> rx.Component:
    return rx.box(
        rx.box( # Card Header
            rx.text(heading, size="4", color="gray", weight="bold")
        ),
        rx.vstack( # Card Content
            rx.text(content, size="5", weight="bold"),
            rx.text(supplementary_text, size="1", color="gray"),
            margin_top="2rem"
        ),
        border="1px solid",
        border_color="grey",
        border_radius=".5rem",
        box_shadow="0 4px 12px rgba(0,0,0,0.08)",
        padding="1.3rem",
        # max_width="350px"
    )

def added_agent_tile(agent: AgentModelView) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.box(
                rx.hstack(
                    rx.text(agent.identity, size="5", weight="bold"),
                    added_agent_status("deployed"),
                    spacing="2",
                    align="center",
                    justify="center"
                ),
            ),
            rx.hstack(
                rx.button(
                    rx.icon("settings", size=16),
                    rx.text("Configure"),
                    on_click=lambda: NavigationState.route_to_agent_config(
                        State.current_uid,
                        agent.identity,
                        agent
                    ),
                    size="1"
                ),
                rx.button(
                    rx.icon("trash-2", size=16),
                    rx.text("Remove"),
                    variant="outline",
                    color_scheme="red",
                    on_click=lambda: State.handle_removing_agent(agent.identity),
                    size="1"
                ),
                spacing="2"
            ),
            justify="between",
            align="center",
            width="100%"
        ),
        width="100%",
        border="1px solid",
        border_color="grey",
        border_radius=".5rem",
        box_shadow="0 4px 12px rgba(0,0,0,0.08)",
        padding=".75rem",
    )

def added_agent_status(config_state: str) -> rx.Component:
    """
        A small status indicator for added agents on the added agents tile.
        Parameters:
            config_state (str): The state of the agent configuration. Can be "draft"
              "pending", or "deployed".
    """
    return rx.badge(
        config_state,
        color_scheme=rx.cond(
            config_state == "draft",
            "orange",
            rx.cond(
                config_state == "pending",
                "blue",
                "gray"
            )
        ),
        variant="surface",
        radius="medium",
        size="2"
    )

def add_agent_tile(agent: AgentModelView) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.box(
                rx.hstack(
                    rx.text(agent.identity, size="5", weight="bold"),
                    spacing="2",
                    align="center"
                ),
                # rx.text(description, size="2", color="gray"),
            ),
            rx.button(
                rx.icon("plus", size=16),
                rx.text("Add"),
                on_click=lambda: State.handle_adding_agent(agent, State.current_uid),
                size="1"
            ),
            justify="between",
            align="center",
            width="100%"
        ),
        width="100%",
        border="1px solid",
        border_color="grey",
        border_radius=".5rem",
        box_shadow="0 4px 12px rgba(0,0,0,0.08)",
        padding=".75rem",
    )

def get_status_cell(status: str) -> rx.Component:
    status_check = status.lower().strip()
    return rx.cond(
        status_check == "healthy",
        rx.badge(
            "Healthy",
            variant="soft",
            size="2",
            color_scheme="green",
        ),
        rx.badge(
            "Unhealthy",
            variant="solid",
            size="2",
            color_scheme="red",
        ),
    )

def get_state_cell(state: str) -> rx.Component:
    state_check = state.lower().strip()
    return rx.cond(
        state_check == "running",
        rx.badge(
            "Running",
            variant="soft",
            size="2",
        ),
        rx.badge(
            "Stopped",
            variant="outline",
            size="2",
            color_scheme="gray",
        ),
    )

def render_agent_row(agent: AgentModelView) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.vstack(
                rx.text(agent.identity, size="3", weight="bold"),
                # rx.text("Agent Description", size="1", color="gray"),
                spacing="1"
            )
        ),
        rx.table.cell(
            get_status_cell("Unhealthy")
        ),
        rx.table.cell(
            get_state_cell("Stopped")
        ),
        #TODO we need an api call to get the pip version
        rx.table.cell(
            "1.2.3"
        ),
        #TODO we need an api cal for this information
        rx.table.cell(
            rx.text("2 min ago", color="gray")
        ),
        render_agent_actions_cell(agent)
    )

def render_agent_actions_cell(agent: AgentModelView) -> rx.Component:
    return rx.table.cell(
        rx.hstack(
            rx.button(
                rx.icon("square", size=16),
                rx.text("Stop"),
                variant="outline"
            ),
            agent_actions_dropdown(agent),
            spacing="4",
            align="center"
        )
    )

def agent_actions_dropdown(agent: AgentModelView) -> rx.Component:
    return rx.menu.root(
        rx.menu.trigger(
            rx.button(
                rx.icon("ellipsis", size=16),
                variant="ghost",
                color_scheme="gray"
            )
        ),
        rx.menu.content(
            rx.menu.item(
                rx.hstack(
                    rx.icon("settings", size=16),
                    rx.text("Configure"),
                    align="center",
                    spacing="2"
                ),
                on_click=lambda: NavigationState.route_to_agent_config(
                    State.current_uid,
                    agent.identity,
                    agent
                )
            ),
            rx.menu.item(
                "View Logs",
            ),
            rx.separator(),
            rx.menu.item(
                "Restart Agent",
                color_scheme="blue"
            ),
            rx.menu.item(
                "Delete Agent",
                color_scheme="red"
            )
        )
    )

def configuration_problem_tooltip() -> rx.Component:
    return rx.hover_card.root(
        rx.hover_card.trigger(
            rx.text(
                "One or more problems with the current configuration.",
                text_decoration="underline", 
                color_scheme="red",
                cursor="pointer",
                size="2"
            )
        ),
        rx.hover_card.content(
            rx.vstack(
                rx.foreach(
                    State.working_platform.configuration_problems,
                    lambda problem: configuration_problem(problem_text=problem.message, tab=problem.tab)
                ),
                spacing="4",
            )
        )
    )

def configuration_problem(problem_text: str, tab: str) -> rx.Component:
    return rx.hstack(
        rx.icon("triangle-alert", size=20, color=rx.color("red", 10)),
        rx.text(
            problem_text,
            color_scheme="red",
            size="2",
            text_decoration="underline"
        ),
        cursor="pointer",
        spacing="2",
        on_click=State.set_platform_tab(tab),
        align="center"
    )

@rx.page(route="/platform/[uid]", on_load=State.hydrate_state)
def platform_page() -> rx.Component:
    return rx.box(
        rx.vstack(
            header(
                rx.hstack(
                    icon_button_wrapper.icon_button_wrapper(
                        tool_tip_content="Go back to overview",
                        icon_key="arrow-left",
                        on_click=lambda: NavigationState.route_to_index()
                    ),
                    rx.text(f"""{
                            rx.cond(
                                State.working_platform.new_instance,
                                'New Platform',
                                f'Platform: {State.platform_title}'
                            )
                        }""",
                        trim="both",
                        size="6"
                    ),
                    spacing="6",
                    align="center",
                ),
                rx.hstack(
                    rx.cond(
                        State.working_platform.new_instance==False,
                        rx.fragment(
                            rx.button(
                                # rx.icon(""),
                                rx.text(
                                    rx.cond(
                                        State.platform_deployed,
                                        "Re-Deploy",
                                        "Deploy"
                                    )
                                ),
                            ),
                            rx.button(
                                # rx.icon(""),
                                rx.text(
                                    "Pause"
                                ),
                                disabled=rx.cond(
                                    State.platform_deployed,
                                    False,
                                    True
                                )
                            ),
                            rx.divider(orientation="vertical", size="2"),
                            icon_button_wrapper.icon_button_wrapper(
                                tool_tip_content="Copy Platform",
                                icon_key="copy",
                                on_click=lambda: State.copy_platform(State.current_uid)
                            )
                        )
                    ),
                    icon_button_wrapper.icon_button_wrapper(
                        tool_tip_content="Delete platform",
                        icon_key="trash-2",
                    ),
                ),
                justify="between",
                width="100%",
            ),
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger(
                        "Status", value="status", disabled=rx.cond(
                            State.working_platform.platform.in_file,
                            False,
                            True
                        )
                    ),
                    rx.tabs.trigger("Connection", value="connection"),
                    rx.tabs.trigger("Instance Configuration", value="instance_configuration"),
                    rx.tabs.trigger("Agent Configuration", value="agent_configuration"),
                ),
                rx.tabs.content(
                    status_tab(),
                    padding_y="1.5rem",
                    value="status"
                ),
                rx.tabs.content(
                    connection_tab(),
                    padding_y="1.5rem",
                    value="connection"
                ),
                rx.tabs.content(
                    instance_configuration_tab(),
                    padding_y="1.5rem",
                    value="instance_configuration"
                ),
                rx.tabs.content(
                    agent_configuration_tab(),
                    padding_y="1.5rem",
                    value="agent_configuration"
                ),
                width="100%",
                value=State.working_platform.selected_tab,
                on_change=lambda: State.set_platform_tab
            ),
            width="100%",
            max_width="1200px",
            margin_left="auto",
            margin_right="auto",
            padding_y="1.5rem",
        ),
        height="100vh",
        width="100%",
        overflow_y="auto",
        padding_x="16px",
    )


def platform_pagea() -> rx.Component:

    # State.working_platform: Instance = State.platforms[State.current_uid]

    return rx.cond(
        State.is_hydrated, 
        rx.fragment(
            app_layout(
                header(
                rx.hstack(
                    icon_button_wrapper.icon_button_wrapper(
                        tool_tip_content="Go back to overview",
                        icon_key="arrow-left",
                        on_click=lambda: NavigationState.route_to_index()
                    ),
                    rx.text(f"""{
                            rx.cond(
                                State.working_platform.new_instance,
                                'New Platform',
                                f'Platform: {State.platform_title}'
                            )
                        }""",
                        trim="both",
                        size="6"
                    ),
                    spacing="6",
                    align="center",
                ),
                rx.hstack(
                    rx.cond(
                        State.working_platform.new_instance==False,
                        icon_button_wrapper.icon_button_wrapper(
                            tool_tip_content="Copy Platform",
                            icon_key="copy",
                            on_click=lambda: State.copy_platform(State.current_uid)
                        )
                    ),
                    icon_button_wrapper.icon_button_wrapper(
                        tool_tip_content="Delete platform",
                        icon_key="trash-2",
                    ),
                ),
                justify="between"
            ),
            platform_tabs()
            )
        ),
        # Skeleton Stuff
        rx.vstack(
            # Header
            rx.hstack(
                rx.hstack(
                    rx.skeleton(
                        rx.box(),
                        height="3rem",
                        width="5rem",
                        radius="5rem",
                        loading=True,
                    ),
                    rx.skeleton(
                        rx.box(),
                        height="3rem",
                        width="12rem",
                        radius="5rem",
                        loading=True,
                    ),
                    spacing="4",
                    align="center",
                ),
                rx.skeleton(
                    rx.box(),
                    height="3rem",
                    width="5rem",
                    radius="5rem",
                    loading=True,
                ),
                spacing="4",
                align="center",
                justify="between",
                width="100%",
            ),
            # Tabs divider
            rx.skeleton(
                rx.box(),
                width="100%",
                height="15px",
                loading=True,
            ),
            spacing="6",
            padding="1rem"
        )
    )

def platform_tabs() -> rx.Component:
    # State.working_platform: Instance = State.platforms[State.current_uid]
    return rx.cond(
        State.is_hydrated,
        rx.box(
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger(
                        "Status", value="status", disabled=rx.cond(
                            State.working_platform.platform.in_file,
                            False,
                            True
                        )
                    ),
                    rx.tabs.trigger("Configuration", value="configuration"),
                ),
                rx.tabs.content(
                    data_tab_content(),
                    value="status"
                ),
                rx.tabs.content(
                    rx.box(
                        configuration_tab_content(),
                        padding="1rem"
                    ),
                    value="configuration"
                ),
                default_value=rx.cond(
                    State.working_platform.platform.in_file,
                    "status",
                    "configuration"
                )
            )
        )
    )

# Config tab and it's components:
def configuration_tab_content() -> rx.Component:
    # State.working_platform: Instance = State.platforms[State.current_uid]
    
    return rx.cond(State.is_hydrated, 
            rx.box(
                rx.accordion.root(
                    rx.accordion.item(
                        header="Connection",
                        value="connection",
                        # content=rx.box(
                        #     connection_accordion_content(State.working_platform)
                        # ),
                        content=rx.box(
                            rx.box(
                                form_entry.form_entry(
                                    "Host",
                                    rx.input(
                                        value= State.form_ansible_host,
                                        on_change=lambda v: State.update_form_host_field("ansible_host", v),
                                        size="3",
                                        required=True,
                                        on_blur=lambda: State.determine_host_reachability(),
                                        color_scheme = rx.cond(
                                            State.is_host_resolvable,
                                            "gray",
                                            "red"
                                        )
                                    ),
                                    required_entry=True,
                                    upload=rx.cond(
                                        State.host_pinging,
                                        rx.spinner(),
                                        rx.cond(
                                            State.is_host_resolvable,
                                            tile_icon(
                                                "check"
                                            ),
                                            tile_icon(
                                                "triangle-alert"
                                            )
                                        )
                                    ),
                                    below_component=rx.fragment(
                                        rx.cond(
                                            State.form_error_ansible_host != "",
                                            rx.text(
                                                State.form_error_ansible_host,
                                                color_scheme="red"
                                            )
                                        ),
                                        rx.cond(
                                            State.is_host_resolvable == False,
                                            rx.text(
                                                "Host must be a valid domain or ip address", 
                                                color_scheme="red"
                                            )
                                        )
                                    ),
                                ),
                                form_entry.form_entry(
                                    "Username",
                                    rx.input(
                                        value= State.form_ansible_user,
                                        on_change=lambda v: State.update_form_host_field("ansible_user", v),
                                        size="3",
                                        required=True,
                                    ),
                                    upload=tile_icon(
                                        "badge-info",
                                        tooltip="Username must have SUDO permissions"
                                    ),
                                    required_entry=True,
                                    below_component=rx.cond(
                                        State.form_error_ansible_user != "",
                                        rx.text(
                                            State.form_error_ansible_user,
                                            color_scheme="red"
                                        )
                                    ),
                                ),
                                form_entry.form_entry(
                                    "Port SSH",
                                    rx.input(
                                        value= State.form_ansible_port,
                                        on_change=lambda v: State.update_form_host_field("ansible_port", v),
                                        size="3",
                                        required=True,
                                    ),
                                    required_entry=True,
                                    below_component=rx.cond(
                                        State.form_error_ansible_port != "",
                                        rx.text(
                                            State.form_error_ansible_port,
                                            color_scheme="red"
                                        )
                                    ),
                                ),
                                rx.box(
                                    rx.hstack(
                                        rx.text("Toggle Advanced"),
                                        rx.cond(
                                            State.working_platform.advanced_expanded,
                                            rx.icon("chevron-up"),
                                            rx.icon("chevron-down")
                                        )
                                    ),
                                    class_name="toggle_advanced_button",
                                    on_click=lambda: State.toggle_advanced(State.current_uid)
                                ),
                                rx.cond(
                                    State.working_platform.advanced_expanded,
                                    rx.fragment(
                                        form_entry.form_entry(
                                            "HTTP Proxy",
                                            rx.input(
                                                value= State.form_http_proxy,
                                                on_change=lambda v: State.update_form_host_field("http_proxy", v),
                                                size="3",
                                                required=True,
                                            ),
                                            below_component=rx.cond(
                                                State.form_error_http_proxy != "",
                                                rx.text(
                                                    State.form_error_http_proxy,
                                                    color_scheme="red"
                                                )
                                            ),
                                        ),
                                        form_entry.form_entry(
                                            "HTTPS Proxy",
                                            rx.input(
                                                value= State.form_https_proxy,
                                                on_change=lambda v: State.update_form_host_field("https_proxy", v),
                                                size="3",
                                                required=True,
                                            ),
                                            below_component=rx.cond(
                                                State.form_error_https_proxy != "",
                                                rx.text(
                                                    State.form_error_https_proxy,
                                                    color_scheme="red"
                                                )
                                            ),
                                        ),
                                        form_entry.form_entry(
                                            "VOLTTRON Home",
                                            rx.input(
                                                value= State.form_volttron_home,
                                                on_change=lambda v: State.update_form_host_field("volttron_home", v),
                                                size="3",
                                                required=True,
                                            ),
                                            below_component=rx.cond(
                                                State.form_error_volttron_home != "",
                                                rx.text(
                                                    State.form_error_volttron_home,
                                                    color_scheme="red"
                                                )
                                            ),
                                        ),
                                    )
                                ),
                                class_name="platform_content_view"
                            ),
                            class_name="platform_content_container"
                        )
                    ),
                    rx.accordion.item(
                        header="Instance Configuration",
                        value="instance_configuration",
                        # content=rx.box(
                        #     instance_configuration_accordion_content(State.working_platform)
                        # ),
                        content=rx.box(
                            rx.box(
                                form_entry.form_entry( # validate
                                    "Instance Name",
                                    rx.vstack(
                                        rx.input(
                                            size="3",
                                            value=State.form_instance_name,
                                            on_change=lambda v: State.update_form_platform_field("instance_name", v),
                                            required=True,
                                        ),
                                        align="center"
                                    ),
                                    below_component=rx.fragment(
                                        rx.cond(
                                            State.form_error_instance_name != "",
                                            rx.text(
                                                State.form_error_instance_name,
                                                color_scheme="red"
                                            )
                                        ),
                                        rx.cond(
                                            State.platform_instance_name_not_in_use == False,
                                            rx.text(
                                                "Instance Name already in use", 
                                                color_scheme="red"
                                            )
                                        )
                                    ),
                                    required_entry=True,
                                    upload=tile_icon(
                                        "badge-info",
                                        tooltip="Instance Name must contain only letters, numbers, hyphens, and underscores"
                                    )
                                ),
                                form_entry.form_entry( # validate
                                    "Vip Address",
                                    rx.vstack(
                                        rx.input(
                                            size="3",
                                            value=State.form_vip_address,
                                            on_change=lambda v: State.update_form_platform_field("vip_address", v),
                                            required=True,
                                        ),  
                                        align="center"
                                    ),
                                    below_component=rx.cond(
                                        State.form_error_vip_address != "",
                                        rx.text(
                                            State.form_error_vip_address,
                                            color_scheme="red"
                                        )
                                    ),
                                    required_entry=True,
                                    upload=tile_icon(
                                        "badge-info",
                                        tooltip="Vip Address must be in the format tcp://<ip>:<port>"
                                    )
                                ),
                                form_entry.form_entry(
                                    "Member of Federation",
                                    rx.vstack(
                                        rx.checkbox(
                                            size="3",
                                            on_click = lambda: State.toggle_federation()
                                        ),
                                        justify="center",
                                        align="center",
                                        width="100%"
                                    )
                                ),
                                form_entry.form_entry(
                                    "Web",
                                    rx.vstack(
                                        rx.checkbox(
                                            size="3",
                                            checked=State.working_platform.web_checked,
                                            on_change=lambda: State.toggle_web()
                                        ),
                                        justify="center",
                                        align="center",
                                        width="100%"
                                    )
                                ),
                                rx.cond(
                                    State.working_platform.web_checked,
                                    rx.fragment(
                                        form_entry.form_entry(
                                            "Web Bind Address",
                                            rx.input(
                                                size="3",
                                                value=State.form_web_bind_address,
                                                on_change=lambda v: State.update_form_platform_field("web_bind_address", v),
                                                required=True,
                                            ),
                                            below_component=rx.cond(
                                                State.form_error_web_bind_address != "",
                                                rx.text(
                                                    State.form_error_web_bind_address,
                                                    color_scheme="red"
                                                )
                                            ),
                                        )
                                    )
                                ),
                                rx.box(
                                    rx.hstack(
                                        rx.text("Agent Configuration"),
                                        rx.cond(
                                            State.working_platform.agent_configuration_expanded,
                                            rx.icon("chevron-up"),
                                            rx.icon("chevron-down")
                                        )
                                    ),
                                    class_name="toggle_advanced_button",
                                    on_click=lambda: State.toggle_agent_config_details()
                                ),
                                rx.box(
                                    rx.cond(
                                        State.working_platform.agent_configuration_expanded,
                                        rx.el.div(
                                            rx.box(
                                                rx.box(
                                                    rx.heading("Listed Agents", as_="h3"),
                                                    rx.foreach(
                                                        State.list_of_agents,
                                                        lambda agent, index: config_tile.config_tile(
                                                            agent.identity,
                                                            right_component=tile_icon(
                                                                "plus",
                                                                on_click=lambda: State.handle_adding_agent(agent, State.current_uid)
                                                            ),
                                                        ),
                                                    ),
                                                    class_name="agent_config_view_content"
                                                ),
                                                class_name="agent_config_views"
                                            ),
                                            rx.box(
                                                rx.box(
                                                    rx.heading("Added Agents", as_="h3"),
                                                    rx.foreach(
                                                        State.working_platform.platform.agents,
                                                        lambda identity_agent_pair: config_tile.config_tile(
                                                            identity_agent_pair[1].identity,
                                                            left_component=tile_icon(
                                                                "trash-2",
                                                                on_click= lambda: State.handle_removing_agent(identity_agent_pair[0])
                                                                # on_click= lambda: State.handle_removing_agent(identity_agent_pair[0])
                                                            ),
                                                            right_component=tile_icon(
                                                                "settings",
                                                                on_click=lambda: NavigationState.route_to_agent_config(
                                                                    State.current_uid,
                                                                    identity_agent_pair[1].routing_id,
                                                                    identity_agent_pair[1]
                                                                )
                                                            ),
                                                            # This works but i dont want to implement it just yet, i want more info on how
                                                            # this should ideally work
                                                            # class_name=rx.cond(
                                                            #     State.new_agents_list.contains(identity_agent_pair[1].routing_id),
                                                            #     "agent_config_tile new",
                                                            #     "agent_config_tile"
                                                            # ),
                                                            # tooltip=rx.cond(
                                                            #     State.new_agents_list.contains(identity_agent_pair[1].routing_id),
                                                            #     "This agent is loaded with default configs",
                                                            #     ""
                                                            # )
                                                        )
                                                    ),
                                                    class_name="agent_config_view_content"
                                                ),
                                                class_name="agent_config_views"
                                            ),
                                            class_name="agent_config_container"
                                        ),
                                    )
                                ),
                                class_name="platform_content_view"
                            ),
                            class_name="platform_content_container"
                        )
                    ),
                    collapsible=True,
                    default_value=["connection"],
                    type="multiple",
                    variant="outline"
                ),
                rx.box(
                    rx.button(
                        "Save", 
                        size="4", 
                        variant="surface",
                        color_scheme="green",
                        on_click=lambda: State.handle_save(),
                        disabled=rx.cond(
                            (State.instance_savable)
                            & (State.instance_uncaught),
                            # (State.working_platform.uncaught),
                            False,
                            True
                        )
                    ),
                    rx.dialog.root(
                        rx.dialog.trigger(
                            rx.button(
                                rx.cond(
                                    State.platform_deployed,
                                    "Re-Deploy",
                                    "Deploy"
                                ), 
                                size="4", 
                                variant="surface", 
                                color_scheme="blue",
                                disabled=rx.cond(
                                    (State.instance_uncaught == False)
                                    & (State.instance_deployable==True),
                                    False,
                                    True
                                )
                            ),
                        ),
                        rx.dialog.content(
                            rx.dialog.title("Password Required"),
                            rx.dialog.description("To deploy, please provide your ssh password"),
                            rx.vstack(
                                rx.vstack(
                                    form_entry.form_entry(
                                        "Password",
                                        rx.input(
                                            type="password",
                                            on_change=State.update_password_field,
                                            value=State.password_field
                                        ),
                                        required_entry=True
                                    ),
                                    align="center",
                                    justify="center"
                                ),
                                rx.hstack(
                                    rx.dialog.close(
                                        rx.button(
                                            "Cancel",
                                            variant="soft",
                                            color_scheme="gray",
                                        )
                                    ),
                                    rx.dialog.close(
                                        rx.button(
                                            "Submit",
                                            on_click=lambda: State.handle_deploy(),
                                            disabled=rx.cond(
                                                State.password_field=="",
                                                True,
                                                False
                                            )
                                        )
                                    ),
                                    spacing="3",
                                    justify="end",
                                ),
                                width="100%",
                                padding_top="1rem",
                                spacing="6"
                            )
                        )
                    ),
                    rx.button(
                            "Cancel", 
                            size="4", 
                            variant="surface", 
                            color_scheme="red",
                            on_click=lambda: State.handle_cancel(),
                            disabled=rx.cond(
                                State.instance_uncaught == False,
                                # State.working_platform.uncaught == False,
                                True,
                                False
                            )
                        ),
                    class_name="platform_view_button_row"
                    ),
            class_name="platform_view_container"
            )
        )

# Data tab and it's components
def data_tab_content() -> rx.Component: 
    return rx.cond(State.is_hydrated, rx.container(
        rx.text("this is data... in all of it's glory")
    ))


# General components
def agent_config_tile(text, left_component: rx.Component = False, right_component: rx.Component = False)->rx.Component:
    return rx.hstack(
        rx.cond(
            left_component,
            rx.flex(
                left_component,
                align="center",
                justify="center",
            )
        ),
        rx.flex(
            rx.text(text),
            class_name=f"agent_config_tile",
        ),
        rx.cond(
            right_component,
            rx.flex(        
                right_component,
                align="center",
                justify="center"
            )
        ),  
        spacing="2",
        align="center",
    )
