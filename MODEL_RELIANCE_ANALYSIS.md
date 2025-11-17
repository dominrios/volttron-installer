# Model Reliance Analysis - Platform Page State

## Current State: Hybrid Approach (Form Shadow Pattern)

**Status:** Form state exists but model is still the source of truth during editing.

## Issues Identified

### 1. Model Updates on Every Keystroke ❌

**Location:** `update_form_host_field()` and `update_form_platform_field()`

**Problem:**
```python
# Lines 720-726 in update_form_host_field()
# Also update model for backward compatibility
if field == "ansible_host":
    self._host_resolved = False
    self.update_detail("id", value)  # ❌ Updates model immediately
else:
    self.update_detail(field, value)  # ❌ Updates model immediately
```

**Impact:** Model is updated on every keystroke, causing:
- Unnecessary reactivity
- Model state changes before user is done editing
- Can't distinguish "user is typing" from "user has committed changes"

**Solution:** Remove model updates from form field handlers. Only sync on save/cancel.

---

### 2. Validation Reads from Model, Not Forms ❌

**Location:** Multiple validation methods

**Problem:**
```python
# Line 956 - connection_validity()
def connection_validity(self, working_platform: Instance) -> tuple[bool, dict[str, bool]]:
    # ❌ Reads from model
    if working_platform.host.id == "":
        valid = False
    if working_platform.host.ansible_user == "":
        valid = False
    # ... etc
```

**Impact:** 
- Validation doesn't reflect current form state
- User sees validation errors based on old model data
- Form validation errors are separate from business validation

**Solution:** Create form-based validation methods that read from form state:
```python
def form_connection_validity(self) -> tuple[bool, dict[str, bool]]:
    """Validate connection using form state."""
    valid = True
    validity_map = {}
    
    if self.form_ansible_host == "":
        valid = False
        validity_map["ansible_host"] = False
    
    if self.form_ansible_user == "":
        valid = False
        validity_map["ansible_user"] = False
    
    # ... etc
    return (valid, validity_map)
```

---

### 3. Business Logic Reads from Model ❌

**Location:** `check_instance_savable()`, `check_instance_uncaught()`, `handle_save()`

**Problem:**
```python
# Line 921 - check_instance_savable()
def check_instance_savable(self, working_platform: Instance) -> bool:
    # ❌ Reads from model
    host_dict = working_platform.host.to_dict()
    if host_dict["id"] == "" or host_dict["ansible_user"] == "":
        savable = False
    # ...
```

**Impact:**
- Save button state based on model, not form
- Can't save even if form is valid
- Business logic doesn't know about form state

**Solution:** Check form state for savability:
```python
def check_instance_savable(self) -> bool:
    """Check if instance can be saved using form state."""
    # Check form validation
    if not self.is_form_valid():
        return False
    
    # Check form fields directly
    if (self.form_ansible_host == "" or 
        self.form_ansible_user == "" or
        self.form_instance_name == ""):
        return False
    
    # Check host resolvability
    if not self._host_resolved:
        return False
    
    return True
```

---

### 4. Computed Vars Access Model ❌

**Location:** Multiple `@rx.var` properties

**Problem:**
```python
# Line 353 - connection_validity computed var
@rx.var
def connection_validity(self) -> bool:
    working_platform = self.working_platform
    return self.connection_validity(working_platform)[0]  # ❌ Uses model
```

**Impact:**
- UI reactivity tied to model changes
- Can't show form state in UI
- Computed properties don't reflect current form input

**Solution:** Create form-based computed vars:
```python
@rx.var
def form_connection_valid(self) -> bool:
    """Check if connection form is valid."""
    return (self.form_ansible_host != "" and
            self.form_ansible_user != "" and
            self.form_ansible_port != "" and
            self.form_error_ansible_host == "" and
            self.form_error_ansible_user == "" and
            self.form_error_ansible_port == "")
```

---

### 5. Form State is Not Source of Truth ❌

**Current Pattern:**
```
User types → Form state updates → Model updates immediately → Validation reads model
```

**Desired Pattern:**
```
User types → Form state updates → Validation reads form → Model updates only on save
```

**Impact:**
- Can't have "draft" state separate from committed state
- Model changes before user commits
- Hard to implement "unsaved changes" detection properly

---

## Recommended Refactoring Steps

### Step 1: Remove Model Updates from Form Handlers ✅

**Change:**
```python
@rx.event
def update_form_host_field(self, field: str, value: str):
    # ... validation logic ...
    self.update_form_field(form_field, value, validator)
    
    # ❌ REMOVE THIS:
    # if field == "ansible_host":
    #     self.update_detail("id", value)
    # else:
    #     self.update_detail(field, value)
```

**Result:** Model only updates on save/cancel.

---

### Step 2: Create Form-Based Validation Methods ✅

**Add:**
```python
def form_connection_validity(self) -> tuple[bool, dict[str, bool]]:
    """Validate connection using form state."""
    # Read from form fields, not model
    pass

def form_platform_validity(self) -> tuple[bool, dict[str, bool]]:
    """Validate platform using form state."""
    # Read from form fields, not model
    pass
```

---

### Step 3: Update Business Logic to Use Form State ✅

**Change:**
```python
def check_instance_savable(self) -> bool:
    """Check if instance can be saved - uses form state."""
    # Use form state instead of model
    if not self.is_form_valid():
        return False
    # ... check form fields directly ...
```

---

### Step 4: Update Computed Vars to Use Form State ✅

**Change:**
```python
@rx.var
def instance_savable(self) -> bool:
    """Check if instance can be saved - uses form state."""
    return self.check_instance_savable()  # Now uses form state
```

---

### Step 5: Update Save Handler to Sync Form → Model ✅

**Current:** Model already updated (because of Step 1 issue)

**Change:**
```python
@rx.event
async def handle_save(self):
    # Sync form to model BEFORE saving
    working_platform = self.platforms[self.current_uid]
    self.sync_form_to_model(working_platform, self.ALL_FORM_MAPPING)
    
    # Now proceed with save using model (which now has form data)
    # ... rest of save logic ...
```

---

## Migration Checklist

- [ ] Remove `update_detail()` calls from `update_form_host_field()`
- [ ] Remove `update_platform_config_detail()` calls from `update_form_platform_field()`
- [ ] Create `form_connection_validity()` that reads from form state
- [ ] Create `form_platform_validity()` that reads from form state
- [ ] Update `check_instance_savable()` to use form state
- [ ] Update `check_instance_uncaught()` to use form dirty state
- [ ] Update computed vars to use form-based validation
- [ ] Update `handle_save()` to sync form → model at start
- [ ] Update `handle_cancel()` to sync model → form (already done ✅)
- [ ] Test that form state is source of truth during editing
- [ ] Test that model only updates on save

---

## Benefits After Refactoring

1. **Form state is source of truth** during editing
2. **Model only updates on save** - clear commit boundary
3. **Validation reflects current input** - immediate feedback
4. **Better performance** - no model updates on every keystroke
5. **Clearer separation** - form state vs. committed state
6. **Easier testing** - form state can be tested independently

---

## Current vs. Desired Architecture

### Current (Hybrid Shadow Pattern):
```
┌─────────────┐
│ Form State  │ ──sync on change──> ┌─────────────┐
│             │                     │ Model State │
└─────────────┘                     └─────────────┘
      ▲                                      │
      │                                      │
      └───────────validation reads──────────┘
```

### Desired (Form-First Pattern):
```
┌─────────────┐
│ Form State  │ ──sync on save──> ┌─────────────┐
│ (Source)    │                     │ Model State │
└─────────────┘                     │ (Committed) │
      │                              └─────────────┘
      │
      └───validation reads from form───┘
```

---

## Conclusion

**Yes, there is still significant model reliance.** The form state exists but acts as a "shadow" that immediately syncs to the model. To complete the migration:

1. **Stop updating model on every keystroke**
2. **Make validation read from form state**
3. **Make business logic check form state**
4. **Only sync form → model on save**

This will make form state the true source of truth during editing, with the model only updated when the user commits changes.

