# Form Migration Strategy

## Overview

This document outlines the strategy for migrating from model-based forms to React-like standard form patterns while maintaining app functionality.

## Current State

The app currently uses a model-based approach where:
- Form inputs bind directly to model properties (`State.working_platform.host.ansible_host`)
- Validation happens through model methods
- State updates require model refreshing
- Every page uses this pattern extensively

## Migration Strategy: Hybrid Approach

### Phase 1: Infrastructure (Current)

1. ✅ Created `FormStateMixin` - Provides form state management
2. ✅ Created `ControlledInput` component - React-like controlled inputs
3. ✅ Created `FormField` wrapper - Consistent form field styling

### Phase 2: Gradual Migration

We'll migrate one page at a time, starting with the simplest forms:

1. **Start with Platform Page** (most complex, but most important)
   - Add form state fields alongside existing model state
   - Create field mapping between form and model
   - Migrate inputs one section at a time
   - Keep model sync for backward compatibility

2. **Migration Pattern for Each Form Field:**

```python
# Before (Model-based)
rx.input(
    value=State.working_platform.host.ansible_host,
    on_change=lambda v: State.update_detail("ansible_host", v),
)

# After (Form-based with hybrid support)
ControlledInput(
    state=State,
    field_name="form_ansible_host",
    placeholder="Ansible Host",
    label="Ansible Host",
    on_change=lambda v: State.update_form_field("form_ansible_host", v),
    validation=lambda v: (len(v) > 0, "Ansible host is required"),
)
```

3. **State Class Pattern:**

```python
class PlatformPageState(rx.State, FormStateMixin):
    # Existing model state
    platforms: dict[str, Instance] = {}
    
    # New form state (for new forms)
    form_ansible_host: str = ""
    form_ansible_user: str = ""
    # ... other form fields
    
    # Field mapping for sync
    HOST_FORM_MAPPING = {
        "form_ansible_host": "host.ansible_host",
        "form_ansible_user": "host.ansible_user",
        # ...
    }
    
    @rx.event
    def initialize_form(self):
        """Initialize form from model when page loads."""
        if self.current_uid in self.platforms:
            self.initialize_form_from_model(
                self.working_platform,
                self.HOST_FORM_MAPPING
            )
    
    @rx.event
    def save_form(self):
        """Save form data to model."""
        if self.current_uid in self.platforms:
            self.sync_form_to_model(
                self.working_platform,
                self.HOST_FORM_MAPPING
            )
            # Then proceed with existing save logic
```

### Phase 3: Validation Migration

1. Create validation service:
   - `services/validation_service.py`
   - Move validation logic from state classes
   - Create reusable validators

2. Update form fields to use validators:
   - On-change validation for immediate feedback
   - On-blur validation for final check
   - Display errors inline

### Phase 4: Complete Migration

Once all pages are migrated:
1. Remove model-based form bindings
2. Remove `@rx.var` computed properties that access nested model data
3. Clean up unused model properties
4. Update documentation

## Benefits of This Approach

1. **Gradual Migration**: Can migrate one page at a time
2. **Backward Compatible**: Old code continues to work during migration
3. **React-like Patterns**: Follows standard React form patterns
4. **Better Validation**: Clear separation of validation logic
5. **Easier Testing**: Form state is separate from models
6. **Better Performance**: No constant model refreshing

## Migration Checklist

### Platform Page
- [ ] Add FormStateMixin to PlatformPageState
- [ ] Create form field mappings
- [ ] Migrate Connection tab inputs
- [ ] Migrate Instance Configuration inputs
- [ ] Migrate Advanced Configuration inputs
- [ ] Update save/cancel handlers
- [ ] Test validation

### Agent Config Page
- [ ] Add FormStateMixin to AgentConfigState
- [ ] Migrate agent form fields
- [ ] Migrate config store entry forms
- [ ] Update save handlers

### BACnet Scan Page
- [ ] Add FormStateMixin to BacnetScanState
- [ ] Migrate scan form fields
- [ ] Migrate property read/write forms

### Index Page
- [ ] Review if forms need migration
- [ ] Migrate if applicable

## Notes

- Keep both approaches working during migration
- Test thoroughly after each section migration
- Update one page completely before moving to next
- Document any breaking changes
- Consider creating migration utilities for common patterns

