"""Config store service for validation and format conversion."""
from typing import Optional, Tuple
from ..backend.models import ConfigStoreEntry
from ..model_views import ConfigStoreEntryModelView
from ..utils.validate_content import check_json, check_csv
from ..utils.conversion_methods import json_string_to_csv_string, csv_string_to_json_string


class ConfigStoreService:
    """Service for config store operations following ValidationService patterns."""
    
    @staticmethod
    def validate_path(value: str) -> Tuple[bool, str]:
        """
        Validate config store entry path.
        
        Args:
            value: The path value to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value or not value.strip():
            return False, "Path is required"
        
        # Use the same validation as check_regular_expression from validate_content
        from ..utils.validate_content import check_regular_expression
        if not check_regular_expression(value.strip()):
            return False, "Path must start with a letter or underscore and can only contain letters, numbers, underscores, hyphens, periods, or slashes"
        
        return True, ""
    
    @staticmethod
    def validate_json_value(value: str) -> Tuple[bool, str]:
        """
        Validate JSON value.
        
        Args:
            value: The JSON string to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value or not value.strip():
            return True, ""  # Empty JSON is valid
        
        if not check_json(value):
            return False, "Invalid JSON format"
        
        return True, ""
    
    @staticmethod
    def validate_csv_value(value: str) -> Tuple[bool, str]:
        """
        Validate CSV value.
        
        Args:
            value: The CSV string to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value or not value.strip():
            return True, ""  # Empty CSV is valid
        
        if not check_csv(value):
            return False, "Invalid CSV format"
        
        return True, ""
    
    @staticmethod
    def validate_entry(entry: ConfigStoreEntry) -> Tuple[bool, dict[str, str]]:
        """
        Validate a config store entry.
        
        Args:
            entry: The config store entry to validate
            
        Returns:
            Tuple of (is_valid, errors_dict)
        """
        errors: dict[str, str] = {}
        
        # Validate path
        path_valid, path_error = ConfigStoreService.validate_path(entry.path)
        if not path_valid:
            errors["path"] = path_error
        
        # Validate value based on data type
        if entry.data_type == "JSON":
            value_valid, value_error = ConfigStoreService.validate_json_value(entry.value)
            if not value_valid:
                errors["value"] = value_error
        elif entry.data_type == "CSV":
            value_valid, value_error = ConfigStoreService.validate_csv_value(entry.value)
            if not value_valid:
                errors["value"] = value_error
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_entry_model_view(entry: ConfigStoreEntryModelView) -> Tuple[bool, dict[str, str]]:
        """
        Validate a config store entry model view.
        
        Args:
            entry: The config store entry model view to validate
            
        Returns:
            Tuple of (is_valid, errors_dict)
        """
        errors: dict[str, str] = {}
        
        # Validate path
        path_valid, path_error = ConfigStoreService.validate_path(entry.path)
        if not path_valid:
            errors["path"] = path_error
        
        # Validate value based on data type
        if entry.data_type == "JSON":
            value_valid, value_error = ConfigStoreService.validate_json_value(entry.value)
            if not value_valid:
                errors["value"] = value_error
        elif entry.data_type == "CSV":
            value_valid, value_error = ConfigStoreService.validate_csv_value(entry.value)
            if not value_valid:
                errors["value"] = value_error
        
        return len(errors) == 0, errors
    
    @staticmethod
    def convert_format(entry: ConfigStoreEntry, target_format: str) -> Optional[ConfigStoreEntry]:
        """
        Convert between JSON and CSV formats.
        
        Args:
            entry: The config store entry to convert
            target_format: Target format ("JSON" or "CSV")
            
        Returns:
            Converted ConfigStoreEntry or None if conversion fails
        """
        if target_format not in ["JSON", "CSV"]:
            return None
        
        if entry.data_type == target_format:
            return entry
        
        try:
            if entry.data_type == "JSON" and target_format == "CSV":
                # Convert JSON to CSV
                csv_string = json_string_to_csv_string(entry.value)
                return ConfigStoreEntry(
                    path=entry.path,
                    data_type="CSV",
                    value=csv_string
                )
            elif entry.data_type == "CSV" and target_format == "JSON":
                # Convert CSV to JSON
                json_string = csv_string_to_json_string(entry.value)
                return ConfigStoreEntry(
                    path=entry.path,
                    data_type="JSON",
                    value=json_string
                )
        except Exception:
            return None
        
        return None