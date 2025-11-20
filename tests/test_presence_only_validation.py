"""Tests for presence-only validation using object as wildcard."""

import pytest
import voluptuous as vol

from voluptuous_openapi import convert, OpenApiVersion


def test_required_any_with_object_wildcard():
    """Test Required(Any(...)) with object as wildcard for presence-only validation."""
    schema = vol.Schema({
        # Using object as wildcard - should only validate presence, not types
        vol.Required(vol.Any("simple_field", "complex_field")): object,
        
        # These define the actual types for the fields
        vol.Optional("simple_field"): str,
        vol.Optional("complex_field"): vol.All(int, vol.Range(min=1, max=100)),
        
        # Other fields
        vol.Optional("name"): str,
    })
    
    result = convert(schema)
    
    expected = {
        "type": "object",
        "properties": {
            # Only the Optional fields should define the actual types
            "simple_field": {"type": "string"},
            "complex_field": {"type": "integer", "minimum": 1, "maximum": 100},
            "name": {"type": "string"},
        },
        "required": [],
        "anyOf": [
            # Only presence validation - no type constraints
            {"required": ["simple_field"]},
            {"required": ["complex_field"]},
        ]
    }
    
    assert result == expected


def test_required_any_with_object_wildcard_multiple_groups():
    """Test multiple Required(Any(...)) with object wildcards."""
    schema = vol.Schema({
        # First group: at least one color-related field
        vol.Required(vol.Any("color", "temperature", "brightness")): object,
        # Second group: at least one mode-related field  
        vol.Required(vol.Any("mode", "preset")): object,
        
        # Actual type definitions
        vol.Optional("color"): str,
        vol.Optional("temperature"): int,
        vol.Optional("brightness"): int,
        vol.Optional("mode"): str,
        vol.Optional("preset"): str,
    })
    
    result = convert(schema)
    
    expected = {
        "type": "object",
        "properties": {
            "color": {"type": "string"},
            "temperature": {"type": "integer"},
            "brightness": {"type": "integer"},
            "mode": {"type": "string"},
            "preset": {"type": "string"},
        },
        "required": [],
        "anyOf": [
            # Cartesian product of constraint groups
            {"required": ["color", "mode"]},
            {"required": ["color", "preset"]},
            {"required": ["temperature", "mode"]},
            {"required": ["temperature", "preset"]},
            {"required": ["brightness", "mode"]},
            {"required": ["brightness", "preset"]},
        ]
    }
    
    assert result == expected


def test_mixed_required_any_with_and_without_object():
    """Test mixing Required(Any(...)) with object and with specific types."""
    schema = vol.Schema({
        # Presence-only validation
        vol.Required(vol.Any("field1", "field2")): object,
        # Type validation
        vol.Required(vol.Any("field3", "field4")): str,
        
        # Actual type definitions for presence-only fields
        vol.Optional("field1"): int,
        vol.Optional("field2"): str,
        # The type-validated fields will get their types from Required(Any(...))
        vol.Optional("field3"): str,  # This should be overridden
        vol.Optional("field4"): str,  # This should be overridden
    })
    
    result = convert(schema)
    
    expected = {
        "type": "object",
        "properties": {
            # Presence-only fields keep their Optional types
            "field1": {"type": "integer"},
            "field2": {"type": "string"},
            # Type-validated fields get their types from Required(Any(...))
            "field3": {"type": "string"},
            "field4": {"type": "string"},
        },
        "required": [],
        "anyOf": [
            # Cartesian product of both groups
            {"required": ["field1", "field3"]},
            {"required": ["field1", "field4"]},
            {"required": ["field2", "field3"]},
            {"required": ["field2", "field4"]},
        ]
    }
    
    assert result == expected


def test_backward_compatibility():
    """Test that existing behavior still works when not using object wildcard."""
    schema = vol.Schema({
        vol.Required(vol.Any("color", "temperature")): str,
        vol.Optional("color"): str,
        vol.Optional("temperature"): int,
    })
    
    result = convert(schema)
    
    expected = {
        "type": "object",
        "properties": {
            "color": {"type": "string"},
            "temperature": {"type": "integer"},
        },
        "required": [],
        "anyOf": [
            {"required": ["color"]},
            {"required": ["temperature"]},
        ]
    }
    
    assert result == expected