"""Validation service for form fields."""
from typing import Tuple
import re


class ValidationService:
    """Service for form field validation."""
    
    @staticmethod
    def validate_required(value: str, field_name: str = "Field") -> Tuple[bool, str]:
        """
        Validate that a field is not empty.
        
        Args:
            value: The value to validate
            field_name: Name of the field for error message
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value or value.strip() == "":
            return False, f"{field_name} is required"
        return True, ""
    
    @staticmethod
    def validate_host(value: str) -> Tuple[bool, str]:
        """
        Validate host address (IP or domain).
        
        Args:
            value: The host value to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value or value.strip() == "":
            return False, "Host is required"
        
        # Basic validation - IP or domain
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        
        if re.match(ip_pattern, value) or re.match(domain_pattern, value):
            return True, ""
        
        return False, "Host must be a valid IP address or domain name"
    
    @staticmethod
    def validate_port(value: str) -> Tuple[bool, str]:
        """
        Validate port number.
        
        Args:
            value: The port value to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value or value.strip() == "":
            return False, "Port is required"
        
        try:
            port = int(value)
            if 1 <= port <= 65535:
                return True, ""
            return False, "Port must be between 1 and 65535"
        except ValueError:
            return False, "Port must be a number"
    
    @staticmethod
    def validate_vip_address(value: str) -> Tuple[bool, str]:
        """
        Validate VIP address format (tcp://ip:port).
        
        Args:
            value: The VIP address to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value or value.strip() == "":
            return False, "VIP address is required"
        
        pattern = r'^tcp://[\d.]+:\d+$'
        if re.match(pattern, value):
            return True, ""
        
        return False, "VIP address must be in format tcp://ip:port"
    
    @staticmethod
    def validate_instance_name(value: str) -> Tuple[bool, str]:
        """
        Validate instance name format.
        
        Args:
            value: The instance name to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value or value.strip() == "":
            return False, "Instance name is required"
        
        pattern = r'^[a-zA-Z][a-zA-Z0-9_.-/-]*$'
        if re.match(pattern, value):
            return True, ""
        
        return False, "Instance name must start with a letter and can only contain letters, numbers, underscores, hyphens, periods, or slashes"

