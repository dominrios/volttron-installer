# Component Documentation

This document describes the component structure and usage patterns in the VOLTTRON Installer.

## Component Organization

The components are organized into the following directories:

```
components/
  ├── ui/                    # Reusable UI components
  │   └── buttons/           # Button components
  ├── forms/                 # React-like form components
  ├── form_components/       # Form layout components
  ├── custom_fields/         # Specialized input fields
  ├── tiles/                 # Tile/card components
  ├── header/                # Header components
  ├── sidebar_components/    # Sidebar components
  └── tabs/                  # Tab components
```

## Component Categories

### UI Components (`ui/`)

Reusable, presentational components that don't contain business logic.

#### Buttons (`ui/buttons/`)

- **`icon_button_wrapper`** - Wrapper for icon buttons with consistent styling
- **`icon_upload`** - Upload button with icon
- **`tile_icon`** - Icon for tiles/cards
- **`add_icon_button`** - Add button with icon
- **`delete_icon_button`** - Delete button with icon
- **`setup_button`** - Setup/configuration button
- **`upload_button`** - File upload button

**Usage:**
```python
from ..components.ui.buttons import icon_button_wrapper, tile_icon

icon_button_wrapper(
    icon=tile_icon("add"),
    on_click=State.handle_add
)
```

### Form Components (`forms/`)

React-like form components that follow controlled component patterns.

#### `ControlledInput`

A controlled input component that manages its own state through props.

**Props:**
- `state` - The state class instance
- `field_name` - Name of the form field in state
- `placeholder` - Placeholder text
- `label` - Field label
- `on_change` - Change handler callback
- `validation` - Optional validation function
- `type` - Input type (default: "text")

**Usage:**
```python
from ..components.forms import ControlledInput

ControlledInput(
    state=State,
    field_name="form_ansible_host",
    placeholder="Ansible Host",
    label="Ansible Host",
    on_change=lambda v: State.update_form_host_field("ansible_host", v)
)
```

#### `FormField`

Wrapper component for consistent form field styling with label and error display.

**Props:**
- `label` - Field label
- `error` - Error message to display
- `children` - Input component(s)

**Usage:**
```python
from ..components.forms import FormField

FormField(
    label="Host Address",
    error=State.form_error_ansible_host,
    children=[
        ControlledInput(...)
    ]
)
```

### Form Layout Components (`form_components/`)

Components for organizing and laying out forms.

- **`form_entry`** - Individual form field entry with label and input
- **`form_tab`** - Tab container for form sections
- **`form_view`** - Main form view container
- **`form_tile_column`** - Column layout for form tiles
- **`form_selection_button`** - Button for form field selection

**Usage:**
```python
from ..components.form_components import form_entry, form_tab

form_entry(
    label="Instance Name",
    input_component=rx.input(
        value=State.form_instance_name,
        on_change=lambda v: State.update_form_platform_field("instance_name", v)
    )
)
```

### Custom Fields (`custom_fields/`)

Specialized input components for specific data types.

- **`csv_field`** - CSV data input field
- **`text_editor`** - Multi-line text editor
- **`editable_text`** - Inline editable text

**Usage:**
```python
from ..components.custom_fields import csv_field, text_editor

csv_field(
    value=State.form_config_value,
    on_change=lambda v: State.update_config_detail("value", v)
)
```

### Tiles (`tiles/`)

Card/tile components for displaying platform and configuration information.

- **`platform_tile`** - Tile displaying platform information
- **`config_tile`** - Tile displaying configuration information

**Usage:**
```python
from ..components.tiles import platform_tile, config_tile

platform_tile(
    platform=State.working_platform,
    on_click=State.handle_platform_select
)
```

### Header (`header/`)

Application header component.

- **`header`** - Main application header

**Usage:**
```python
from ..components.header.header import header

header()
```

### Sidebar Components (`sidebar_components/`)

Sidebar navigation components.

- **`app_sidebar`** - Main application sidebar

### Tabs (`tabs/`)

Tab components for organizing content.

- **`platform_overview`** - Platform overview tab

## Component Design Principles

1. **Presentational Components**: Components should be presentational and receive data via props
2. **No Business Logic**: Business logic stays in state classes, not components
3. **Reusability**: UI components should be reusable across different pages
4. **Consistency**: Similar components should follow consistent patterns
5. **Form State Management**: Form components use `FormStateMixin` for state management

## Migration Notes

- Old model-based form bindings are being migrated to form-based patterns
- New forms should use `ControlledInput` and `FormField` components
- Legacy form components in `form_components/` are still used but will be gradually replaced

## Future Improvements

- Consolidate overlapping button components
- Create more reusable form field components
- Standardize component prop interfaces
- Add TypeScript-style prop validation (when Reflex supports it)

