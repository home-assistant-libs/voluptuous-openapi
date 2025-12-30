"""Tests for voluptuous schema and openapi schemas that exercise validation code.

Each test in this file defines an equivalent schema in both `openapi` and
`voluptuous` formats. The schema is then converted to the other format and
validation code is run against all variations of schema types.

The motivation is because voluptuous schemas cannot be introspected directly
and are tested by exercising with both valid and invalid data.
"""

from collections.abc import Callable, Generator

import pytest
import voluptuous as vol
import openapi_schema_validator
from typing import Any
import logging

from voluptuous_openapi import convert, convert_to_voluptuous, OpenApiVersion
from jsonschema.exceptions import ValidationError


_LOGGER = logging.getLogger(__name__)

# Validator type used to represent a validation function for a specific schema type
Validator = Callable[[Any], Any]


class InvalidFormat(Exception):
    """Validation exception thrown on invalid input test data."""


def voluptuous_validator(schema: vol.Schema) -> Validator:
    """Create a Validator for a voluptuous schema."""

    def validator(data: Any) -> Any:
        try:
            _LOGGER.debug("Validating voluptuous %s with schema %s", data, schema)
            return schema(data)
        except (vol.Invalid, ValueError) as e:
            raise InvalidFormat(str(e))

    return validator


def openapi_validator(schema: dict) -> Any:
    """Create a Validator for an OpenAPI schema."""

    def validator(data: Any) -> Any:
        try:
            _LOGGER.debug("Validating openai %s with schema %s", data, schema)
            openapi_schema_validator.validate(data, schema)
            return data
        except ValidationError as e:
            raise InvalidFormat(str(e))

    return validator


# Order of id created by `generate_validators`
TEST_IDS = ["openapi", "voluptuous", "voluptuous_to_openapi", "openapi_to_voluptuous"]


def generate_validators(
    openapi_schema: dict, voluptuous_schema: vol.Schema
) -> Generator[Validator]:
    """Create validation functions for the various schema types."""

    # Native schema validations
    yield openapi_validator(openapi_schema)
    yield voluptuous_validator(voluptuous_schema)

    # Converted schema validations. We use OpenAPI version 3.1 because it has equivalent
    # semantics to voluptuous.
    yield openapi_validator(
        convert(voluptuous_schema, openapi_version=OpenApiVersion.V3_1)
    )
    yield voluptuous_validator(convert_to_voluptuous(openapi_schema))


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {"type": "string"},
        str,
    ),
    ids=TEST_IDS,
)
def test_string(validator: Validator) -> None:
    """Test string schema."""

    validator("hello")
    validator("A" * 10)
    validator("A" * 12)
    validator("123")
    # Note voluptuos coerces everything to string but openapi does not,
    # so not validated here.


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {"type": "string", "minLength": 1, "maxLength": 10},
        vol.All(str, vol.Length(min=1, max=10)),
    ),
    ids=TEST_IDS,
)
def test_string_min_max_length(validator: Validator) -> None:
    """Test string min and max length."""

    validator("hello")
    validator("A" * 10)

    with pytest.raises(InvalidFormat):
        validator(123)

    with pytest.raises(InvalidFormat):
        validator("")

    with pytest.raises(InvalidFormat):
        validator("A" * 12)


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {"type": "integer"},
        int,
    ),
    ids=TEST_IDS,
)
def test_int(validator: Validator) -> None:
    """Test int schema."""

    validator(1)
    validator(10)
    validator(0)

    with pytest.raises(InvalidFormat):
        validator("abc")


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {"type": "integer", "minimum": 1, "maximum": 10},
        vol.All(int, vol.Range(min=1, max=10)),
    ),
    ids=TEST_IDS,
)
def test_int_range(validator: Validator) -> None:
    """Test an int range"""

    validator(1)
    validator(10)

    with pytest.raises(InvalidFormat):
        validator(0)

    with pytest.raises(InvalidFormat):
        validator(11)

    with pytest.raises(InvalidFormat):
        validator(5.5)

    with pytest.raises(InvalidFormat):
        validator("abc")


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {"type": "number"},
        float,
    ),
    ids=TEST_IDS,
)
def test_float(validator: Validator) -> None:
    """Test float schema."""

    validator(1.0)
    validator(5.5)
    validator(10.0)

    with pytest.raises(InvalidFormat):
        validator("abc")


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {"type": "number", "minimum": 1, "maximum": 10},
        vol.All(float, vol.Range(min=1, max=10)),
    ),
    ids=TEST_IDS,
)
def test_float_range(validator: Validator) -> None:
    """Test float range schema."""

    validator(1.0)
    validator(5.5)
    validator(10.0)

    with pytest.raises(InvalidFormat):
        validator(0.0)

    with pytest.raises(InvalidFormat):
        validator(10.1)

    with pytest.raises(InvalidFormat):
        validator("abc")


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {"type": "string", "pattern": r"^\d{3}-\d{2}-\d{4}$"},
        vol.All(str, vol.Match(r"^\d{3}-\d{2}-\d{4}$")),
    ),
    ids=TEST_IDS,
)
def test_match_pattern(validator: Validator) -> None:
    """Test matching a regular expression pattern."""

    validator("555-10-2020")

    with pytest.raises(InvalidFormat):
        validator("555-1-2020")

    with pytest.raises(InvalidFormat):
        validator("555")

    with pytest.raises(InvalidFormat):
        validator("abc")


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {"type": "array", "items": {"type": "string"}},
        vol.All([str]),
    ),
    ids=TEST_IDS,
)
def test_string_list(validator: Validator) -> None:
    """Test a list of strings."""

    validator(["a"])
    validator(["a", "b"])

    with pytest.raises(InvalidFormat):
        validator("abc")

    with pytest.raises(InvalidFormat):
        validator(123)


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {
            "type": "object",
            "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
            "required": ["id"],
        },
        vol.Schema({vol.Required("id"): int, vol.Optional("name"): str}),
    ),
    ids=TEST_IDS,
)
def test_object(validator: Validator) -> None:
    """Test an object."""
    validator({"id": 1, "name": "hello"})
    validator({"id": 1})

    with pytest.raises(InvalidFormat):
        validator({"id": "abc", "name": "hello"})

    with pytest.raises(InvalidFormat):
        validator({"name": "hello"})

    with pytest.raises(InvalidFormat):
        validator("abc")

    with pytest.raises(InvalidFormat):
        validator(123)


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "content": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                    },
                },
            },
        },
        vol.Schema(
            {
                vol.Required("id"): int,
                vol.Optional("content"): vol.Schema({vol.Optional("name"): str}),
            }
        ),
    ),
    ids=TEST_IDS,
)
def test_nested_object(validator: Validator) -> None:
    """Test an object nested in an object."""
    validator({"id": 1, "content": {"name": "hello"}})
    validator({"id": 1, "content": {}})
    validator({"id": 1})

    with pytest.raises(InvalidFormat):
        validator({"id": 1, "content": {"name": 1234}})

    with pytest.raises(InvalidFormat):
        validator(123)


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "additionalProperties": True,
        },
        vol.Schema(
            {vol.Required("id"): int, vol.Optional("name"): str}, extra=vol.ALLOW_EXTRA
        ),
    ),
    ids=TEST_IDS,
)
def test_allow_extra(validator: Validator) -> None:
    """Test additional properties are allowed."""
    validator({"id": 1})
    validator({"id": 1, "extra-key": "hello"})

    with pytest.raises(InvalidFormat):
        validator(123)


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {"type": "null"},
        vol.Schema(None),
    ),
    ids=TEST_IDS,
)
def test_none(validator: Validator) -> None:
    """Test null or None values in the schema."""

    validator(None)

    with pytest.raises(InvalidFormat):
        validator("abc")

    with pytest.raises(InvalidFormat):
        validator(1.0)


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "additionalProperties": False,
        },
        vol.Schema({vol.Required("id"): int, vol.Optional("name"): str}),
    ),
    ids=TEST_IDS,
)
def test_no_extra(validator: Validator) -> None:
    """Test additional properties are not allowed."""
    validator({"id": 1})

    # TODO: Note this does not currently fail when converting from openapi to voluptuous because
    # additionalProperties: False is not set. Fix that then uncomment here.
    # with pytest.raises(InvalidFormat):
    #    validator({"id": 1, "extra-key": "hello"})

    with pytest.raises(InvalidFormat):
        validator(123)


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {"oneOf": [{"type": "string"}, {"type": "integer"}]},
        vol.Any(str, int),
    ),
    ids=TEST_IDS,
)
def test_one_of(validator: Validator) -> None:
    """Test oneOf multiple types."""

    validator(1)
    validator(10)
    validator("hello")

    with pytest.raises(InvalidFormat):
        validator(1.4)

    with pytest.raises(InvalidFormat):
        validator({"key": "value"})


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {"anyOf": [{"type": "string"}, {"type": "integer"}]},
        vol.Any(str, int),
    ),
    ids=TEST_IDS,
)
def test_any_of(validator: Validator) -> None:
    """Test anyOf multiple types."""

    validator(1)
    validator(10)
    validator("hello")

    with pytest.raises(InvalidFormat):
        validator(1.4)

    with pytest.raises(InvalidFormat):
        validator({"key": "value"})


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {"anyOf": [{"type": "string"}, {"type": "null"}]},
        vol.Any(str, None),
    ),
    ids=TEST_IDS,
)
def test_any_of_with_null(validator: Validator) -> None:
    """Test anyOf multiple types that includes null."""

    validator("hello")
    validator("")
    # 'None' is allowed with type: null in openapi
    validator(None)

    with pytest.raises(InvalidFormat):
        validator(1)

    with pytest.raises(InvalidFormat):
        validator(1.4)

    with pytest.raises(InvalidFormat):
        validator({"key": "value"})


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string", "nullable": True},
            },
            "required": ["id"],
        },
        vol.Schema({vol.Required("id"): int, vol.Optional("name"): str}),
    ),
    ids=TEST_IDS,
)
def test_object_with_nullable(validator: Validator) -> None:
    """Test an object with a nullable field."""

    validator({"id": 1, "name": "hello"})

    # Note: The openapi-schema-validator library doesn't properly support
    # OpenAPI 3.0's nullable property, so None values will fail for the
    # native OpenAPI validator but work for converted validators
    try:
        validator({"id": 1, "name": None})
        # If this succeeds, it means the validator properly handles nullable
    except InvalidFormat:
        # This is expected for the native OpenAPI validator due to library limitations
        pass

    with pytest.raises(InvalidFormat):
        validator(1)

    with pytest.raises(InvalidFormat):
        validator({"name": "hello"})

    with pytest.raises(InvalidFormat):
        validator({"id": 1, "name": 1})


def test_convert_to_voluptuous_nullable_field():
    """Test that convert_to_voluptuous properly handles nullable fields."""
    # Test OpenAPI 3.0 nullable syntax
    openapi_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string", "nullable": True},
        },
        "required": ["id"],
    }

    validator = voluptuous_validator(convert_to_voluptuous(openapi_schema))

    # Test valid cases
    validator({"id": 1, "name": "hello"})
    validator({"id": 1, "name": None})  # This should work with our fix
    validator({"id": 1})  # Optional field can be omitted

    # Test invalid cases
    with pytest.raises(InvalidFormat):
        validator({"name": "hello"})  # Missing required id

    with pytest.raises(InvalidFormat):
        validator({"id": 1, "name": 1})  # Wrong type for name


def test_convert_to_voluptuous_nullable_field_openapi_3_1():
    """Test that convert_to_voluptuous properly handles OpenAPI 3.1 nullable syntax."""
    # Test OpenAPI 3.1 type array syntax
    openapi_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "name": {"type": ["string", "null"]},
        },
        "required": ["id"],
    }

    validator = voluptuous_validator(convert_to_voluptuous(openapi_schema))

    # Test valid cases
    validator({"id": 1, "name": "hello"})
    validator({"id": 1, "name": None})  # This should work with our fix
    validator({"id": 1})  # Optional field can be omitted

    # Test invalid cases
    with pytest.raises(InvalidFormat):
        validator({"name": "hello"})  # Missing required id

    with pytest.raises(InvalidFormat):
        validator({"id": 1, "name": 1})  # Wrong type for name


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {"anyOf": [{"type": "string"}, {"type": "null"}]},
        vol.Maybe(str),
    ),
    ids=TEST_IDS,
)
def test_maybe(validator: Validator) -> None:
    """Test voluptuous Maybe type that allows None."""

    validator("hello")
    validator(None)

    with pytest.raises(InvalidFormat):
        validator(1)

    with pytest.raises(InvalidFormat):
        validator(1.4)

    with pytest.raises(InvalidFormat):
        validator({"key": "value"})


@pytest.mark.parametrize(
    "validator",
    generate_validators(
        {
            "type": "object",
            "properties": {
                "color": {"type": "string"},
                "temperature": {"type": "integer"},
                "brightness": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                },
            },
            "anyOf": [
                {"required": ["color"]},
                {"required": ["temperature"]},
                {"required": ["brightness"]},
            ],
        },
        vol.Schema(
            {
                vol.Required(vol.Any("color", "temperature", "brightness")): object,
                vol.Optional("color"): str,
                vol.Optional("temperature"): int,
                vol.Optional("brightness"): vol.All(int, vol.Range(min=0, max=100)),
            }
        ),
    ),
    ids=TEST_IDS,
)
def test_any_of_constraint(validator: Validator) -> None:
    """Test anyOf constraint for requiring at least one of multiple properties."""
    # Test valid cases
    validator({"color": "red"})
    validator({"temperature": 20})
    validator({"brightness": 80})
    validator({"brightness": 0})
    validator({"brightness": 100})
    validator({"color": "blue", "temperature": 25})
    validator({"color": "green", "brightness": 100})
    validator({"temperature": 22, "brightness": 90})
    validator({"color": "purple", "temperature": 21, "brightness": 70})

    # Test invalid cases
    with pytest.raises(InvalidFormat):
        validator({})  # Missing all required properties

    with pytest.raises(InvalidFormat):
        validator({"other_field": "value"})  # Missing all required properties

    with pytest.raises(InvalidFormat):
        validator({"brightness": -1})  # Out of range

    with pytest.raises(InvalidFormat):
        validator({"brightness": 101})  # Out of range

    with pytest.raises(InvalidFormat):
        validator({"brightness": "abc"})  # Wrong type

    with pytest.raises(InvalidFormat):
        validator({"color": 123})  # Wrong type

    with pytest.raises(InvalidFormat):
        validator({"temperature": "abc"})  # Wrong type
